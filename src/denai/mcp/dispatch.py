"""Dispatch tool_use blocks to the correct MCP server."""

from typing import Any

import structlog

from denai.mcp.pool import McpPool

logger = structlog.get_logger()


async def dispatch(pool: McpPool, tool_use: Any) -> dict[str, Any]:
    """Route a tool_use block to the correct MCP server and return a tool_result."""
    full_name: str = tool_use.name
    server_key, _, tool_name = full_name.partition("__")

    if server_key not in pool.sessions:
        return {
            "type": "tool_result",
            "tool_use_id": tool_use.id,
            "content": f"Error: unknown MCP server '{server_key}'",
            "is_error": True,
        }

    session = pool.sessions[server_key]

    logger.debug("dispatching tool", server=server_key, tool=tool_name)

    result = await session.call_tool(tool_name, arguments=tool_use.input)

    content: str
    if isinstance(result.content, str):
        content = result.content
    else:
        parts: list[str] = []
        for block in result.content:
            if hasattr(block, "text"):
                parts.append(block.text)  # type: ignore[union-attr]
            else:
                parts.append(str(block))
        content = "\n".join(parts)

    return {
        "type": "tool_result",
        "tool_use_id": tool_use.id,
        "content": content,
        "is_error": result.isError or False,
    }
