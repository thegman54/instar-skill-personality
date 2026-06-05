"""
personality_list — list available personality trait categories and counts.

Lightweight query that returns category names and trait counts without
loading actual trait content. Useful for the bot to understand what
personality dimensions are available.
"""

import structlog

from ..base import BaseTool, ToolResult
from ..registry import register_tool

log = structlog.get_logger()


@register_tool
class PersonalityListTool(BaseTool):
    """List available personality trait categories."""

    @property
    def name(self) -> str:
        return "personality_list"

    @property
    def description(self) -> str:
        return (
            "List available personality trait categories and their counts. "
            "Use this to see what personality dimensions are configured "
            "without loading full trait content."
        )

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    def credential_keys(self) -> list[str]:
        return []

    async def execute(self, **kwargs) -> ToolResult:
        from ...db import get_pool

        pool = get_pool()
        if not pool:
            return ToolResult.fail("Database not available")

        profile_slug = getattr(self, '_profile_slug', None) or "default"

        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT
                        category,
                        COUNT(*) AS total,
                        COUNT(*) FILTER (WHERE stable = TRUE) AS stable_count,
                        COUNT(*) FILTER (WHERE stable = FALSE) AS dynamic_count
                    FROM personality_traits
                    WHERE profile_slug = $1
                    GROUP BY category
                    ORDER BY category
                    """,
                    profile_slug,
                )

            categories = [
                {
                    "category": row['category'],
                    "total": row['total'],
                    "stable": row['stable_count'],
                    "dynamic": row['dynamic_count'],
                }
                for row in rows
            ]

            return ToolResult.ok({
                "profile": profile_slug,
                "categories": categories,
                "total_traits": sum(c['total'] for c in categories),
            })

        except Exception as e:
            log.error("personality_list_error", error=str(e))
            return ToolResult.fail(f"Failed to list categories: {e}")
