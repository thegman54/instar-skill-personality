"""
personality_read — retrieve a minimal personality trait slice for the current situation.

Returns stable identity traits (always) plus top-ranked situational traits
matching the provided context tags. Traits are weighted by base weight and
time decay (non-stable traits lose ~5% per day since last update).
"""

import hashlib

import structlog

from ..base import BaseTool, ToolResult
from ..registry import register_tool

log = structlog.get_logger()


@register_tool
class PersonalityReadTool(BaseTool):
    """Retrieve personality traits for the current conversation context."""

    @property
    def name(self) -> str:
        return "personality_read"

    @property
    def description(self) -> str:
        return (
            "Load your personality traits for this conversation. "
            "Pass a comma-separated situation string describing the context "
            "(e.g. 'coding,debugging,backend' or 'casual,brainstorming'). "
            "Returns traits grouped by category: identity, tone, stance, "
            "boundary, phrase, situational. Call once at the start of each "
            "new conversation."
        )

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "situation": {
                    "type": "string",
                    "description": (
                        "Comma-separated context tags describing the conversation situation. "
                        "Examples: 'coding,debugging', 'casual,planning', 'technical,review'"
                    ),
                },
                "limit": {
                    "type": "integer",
                    "description": "Max number of non-stable traits to return. Default 15.",
                    "default": 15,
                },
            },
            "required": [],
        }

    def credential_keys(self) -> list[str]:
        return []

    async def execute(self, situation: str = "general", limit: int = 15, **kwargs) -> ToolResult:
        from ...db import get_pool

        pool = get_pool()
        if not pool:
            return ToolResult.fail("Database not available — personality traits require database access")

        # Get profile slug from session context
        profile_slug = getattr(self, '_profile_slug', None) or "default"
        tags = [t.strip() for t in situation.split(",") if t.strip()]

        log.info("personality_read", profile=profile_slug, situation=situation, tags=tags)

        try:
            async with pool.acquire() as conn:
                # Always include stable traits (core identity)
                stable_rows = await conn.fetch(
                    """
                    SELECT category, content
                    FROM personality_traits
                    WHERE profile_slug = $1 AND stable = TRUE
                    ORDER BY category, weight DESC
                    """,
                    profile_slug,
                )

                # Situational traits: match tags, rank by effective weight (decay on read)
                # Decay formula: weight * 0.95 ^ (age_in_days)
                # Always include tone and stance even without tag match
                if tags:
                    situational_rows = await conn.fetch(
                        """
                        SELECT category, content,
                            weight * POWER(0.95, EXTRACT(EPOCH FROM (NOW() - updated_at)) / 86400.0)
                            AS effective_weight
                        FROM personality_traits
                        WHERE profile_slug = $1
                          AND stable = FALSE
                          AND (tags && $2::text[] OR category IN ('tone', 'stance'))
                        ORDER BY effective_weight DESC
                        LIMIT $3
                        """,
                        profile_slug, tags, limit,
                    )
                else:
                    # No tags — return top traits by weight
                    situational_rows = await conn.fetch(
                        """
                        SELECT category, content,
                            weight * POWER(0.95, EXTRACT(EPOCH FROM (NOW() - updated_at)) / 86400.0)
                            AS effective_weight
                        FROM personality_traits
                        WHERE profile_slug = $1
                          AND stable = FALSE
                        ORDER BY effective_weight DESC
                        LIMIT $2
                        """,
                        profile_slug, limit,
                    )

            # Group by category
            result = {}
            for row in stable_rows:
                result.setdefault(row['category'], []).append(row['content'])
            for row in situational_rows:
                result.setdefault(row['category'], []).append(row['content'])

            total = sum(len(v) for v in result.values())
            log.info("personality_read_complete",
                     profile=profile_slug, categories=len(result), traits=total)

            return ToolResult.ok({
                "profile": profile_slug,
                "situation": situation,
                "trait_count": total,
                "traits": result,
            })

        except Exception as e:
            log.error("personality_read_error", error=str(e))
            return ToolResult.fail(f"Failed to read personality traits: {e}")
