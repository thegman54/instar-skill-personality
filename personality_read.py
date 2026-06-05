"""
personality_read — retrieve personality traits for specific categories.

Called by the bot when it decides certain personality categories are relevant
to the current conversation. Returns traits grouped by category, weighted
by base weight and time decay (non-stable traits lose ~5% per day).

The bot's CLAUDE.md lists available categories. The bot picks which ones
matter for the current message and calls this tool with those categories.
"""

import structlog

from ..base import BaseTool, ToolResult
from ..registry import register_tool

log = structlog.get_logger()


@register_tool
class PersonalityReadTool(BaseTool):
    """Retrieve personality traits for specific categories."""

    @property
    def name(self) -> str:
        return "personality_read"

    @property
    def description(self) -> str:
        return (
            "Load personality traits for the given categories. "
            "Your CLAUDE.md lists all available personality categories. "
            "Pass the ones relevant to the current conversation. "
            "Categories you should always include: identity, tone, stance. "
            "Add others (boundary, phrase, situational) when contextually relevant. "
            "Personality traits enhance HOW you respond, not WHAT you respond."
        )

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "categories": {
                    "type": "string",
                    "description": (
                        "Comma-separated category names to load traits for. "
                        "Examples: 'identity,tone,stance' or 'identity,tone,boundary,phrase'"
                    ),
                },
                "situation": {
                    "type": "string",
                    "description": (
                        "Optional comma-separated context tags for situational filtering. "
                        "Examples: 'coding,debugging' or 'casual,planning'"
                    ),
                },
                "limit": {
                    "type": "integer",
                    "description": "Max number of non-stable traits to return per category. Default 10.",
                    "default": 10,
                },
            },
            "required": ["categories"],
        }

    def credential_keys(self) -> list[str]:
        return []

    async def execute(self, categories: str = "", situation: str = "", limit: int = 10, **kwargs) -> ToolResult:
        from ...db import get_pool

        pool = get_pool()
        if not pool:
            return ToolResult.fail("Database not available — personality traits require database access")

        profile_slug = getattr(self, '_profile_slug', None) or "default"
        cat_list = [c.strip() for c in categories.split(",") if c.strip()]
        tags = [t.strip() for t in situation.split(",") if t.strip()] if situation else []

        if not cat_list:
            return ToolResult.fail("No categories specified. Pass at least one category name.")

        log.info("personality_read", profile=profile_slug, categories=cat_list, tags=tags)

        try:
            async with pool.acquire() as conn:
                # Fetch traits for the requested categories
                # Stable traits always included, non-stable filtered by tags if provided
                if tags:
                    rows = await conn.fetch(
                        """
                        SELECT category, content, stable,
                            weight * POWER(0.95, EXTRACT(EPOCH FROM (NOW() - updated_at)) / 86400.0)
                            AS effective_weight
                        FROM personality_traits
                        WHERE profile_slug = $1
                          AND category = ANY($2::text[])
                          AND (stable = TRUE OR tags && $3::text[])
                        ORDER BY category, effective_weight DESC
                        """,
                        profile_slug, cat_list, tags,
                    )
                else:
                    rows = await conn.fetch(
                        """
                        SELECT category, content, stable,
                            weight * POWER(0.95, EXTRACT(EPOCH FROM (NOW() - updated_at)) / 86400.0)
                            AS effective_weight
                        FROM personality_traits
                        WHERE profile_slug = $1
                          AND category = ANY($2::text[])
                        ORDER BY category, effective_weight DESC
                        """,
                        profile_slug, cat_list,
                    )

                # Group by category, limit non-stable per category
                result = {}
                counts = {}  # track non-stable count per category
                for row in rows:
                    cat = row['category']
                    if row['stable']:
                        result.setdefault(cat, []).append(row['content'])
                    else:
                        counts.setdefault(cat, 0)
                        if counts[cat] < limit:
                            result.setdefault(cat, []).append(row['content'])
                            counts[cat] += 1

            total = sum(len(v) for v in result.values())
            log.info("personality_read_complete",
                     profile=profile_slug, categories=len(result), traits=total)

            # Log activity for cockpit visibility
            try:
                from ...db import log_tool_activity
                await log_tool_activity(
                    tool_name="personality_read",
                    summary=f"Loaded {total} traits for categories: {', '.join(cat_list)}",
                    detail={
                        "categories_requested": cat_list,
                        "categories_returned": {k: len(v) for k, v in result.items()},
                        "situation": situation or None,
                        "trait_count": total,
                    },
                    profile_slug=profile_slug,
                    session_id=getattr(self, '_session_id', None),
                )
            except Exception:
                pass

            return ToolResult.ok({
                "profile": profile_slug,
                "categories_requested": cat_list,
                "trait_count": total,
                "traits": result,
            })

        except Exception as e:
            log.error("personality_read_error", error=str(e))
            return ToolResult.fail(f"Failed to read personality traits: {e}")
