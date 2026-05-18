"""Build combined Claude-format tool catalog from all MCP servers."""

from typing import Any

from denai.mcp.pool import McpPool


async def build_catalog(pool: McpPool) -> list[dict[str, Any]]:
    """Build namespaced tool catalog from all connected MCP servers."""
    catalog: list[dict[str, Any]] = []

    for server_key, session in pool.sessions.items():
        listing = await session.list_tools()
        for tool in listing.tools:
            catalog.append(
                {
                    "name": f"{server_key}__{tool.name}",
                    "description": tool.description or "",
                    "input_schema": tool.inputSchema,
                }
            )

    return catalog
