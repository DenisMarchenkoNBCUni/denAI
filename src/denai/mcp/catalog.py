"""Build combined Claude-format tool catalog from all MCP servers."""

from typing import Any

from denai.jira import TOOL_DEFINITION
from denai.mcp.pool import McpPool

EXCLUDED_TOOLS: set[str] = {
    "atlassian__get_my_unresolved_issues",
    "atlassian__get_my_current_sprint_issues",
    "atlassian__search_jira_issues",
    "atlassian__search_issues_by_user_involvement",
    "atlassian__list_issues_by_user_role",
}


async def build_catalog(pool: McpPool) -> list[dict[str, Any]]:
    """Build namespaced tool catalog from all connected MCP servers."""
    catalog: list[dict[str, Any]] = []

    for server_key, session in pool.sessions.items():
        listing = await session.list_tools()
        for tool in listing.tools:
            full_name = f"{server_key}__{tool.name}"
            if full_name in EXCLUDED_TOOLS:
                continue
            catalog.append(
                {
                    "name": full_name,
                    "description": tool.description or "",
                    "input_schema": tool.inputSchema,
                }
            )

    # Add custom tools that bypass broken MCP implementations
    catalog.append(TOOL_DEFINITION)

    return catalog
