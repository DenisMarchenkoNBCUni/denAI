"""Dispatch tool_use blocks to the correct MCP server."""

import asyncio
from typing import Any

import structlog

from denai.jira import TOOL_NAME as JIRA_SEARCH_TOOL, JiraClient
from denai.mcp.pool import McpPool

logger = structlog.get_logger()

MAX_RETRIES = 1
RETRY_DELAY = 1.0
MAX_CONTENT_LENGTH = 80_000

_jira_client: JiraClient | None = None


def init_jira_client(base_url: str, username: str, api_token: str) -> None:
    """Initialize the direct Jira client (called at startup)."""
    global _jira_client
    _jira_client = JiraClient(base_url, username, api_token)


async def _handle_jira_search(tool_use: Any) -> dict[str, Any]:
    """Handle custom jira_search_jql tool directly."""
    if not _jira_client:
        return {
            "type": "tool_result",
            "tool_use_id": tool_use.id,
            "content": "Error: Jira client not initialized",
            "is_error": True,
        }

    args = tool_use.input
    jql = args.get("jql", "")
    max_results = args.get("maxResults", 20)
    fields = args.get("fields", "summary,status,assignee,priority,issuetype,updated")

    data = await _jira_client.search(jql, max_results, fields)
    content = _jira_client.format_results(data)

    return {
        "type": "tool_result",
        "tool_use_id": tool_use.id,
        "content": content,
        "is_error": "error" in data,
    }


async def dispatch(pool: McpPool, tool_use: Any) -> dict[str, Any]:
    """Route a tool_use block to the correct MCP server and return a tool_result."""
    full_name: str = tool_use.name
    server_key, _, tool_name = full_name.partition("__")

    # Custom tool handlers (bypass MCP)
    if tool_name == JIRA_SEARCH_TOOL:
        return await _handle_jira_search(tool_use)

    if server_key not in pool.sessions:
        return {
            "type": "tool_result",
            "tool_use_id": tool_use.id,
            "content": f"Error: unknown MCP server '{server_key}'",
            "is_error": True,
        }

    session = pool.sessions[server_key]

    logger.debug("dispatching tool", server=server_key, tool=tool_name, input=tool_use.input)

    last_error: str | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            result = await session.call_tool(tool_name, arguments=tool_use.input)

            content = _extract_content(result.content)
            is_error = result.isError or False

            if is_error:
                logger.warning(
                    "tool returned error",
                    server=server_key,
                    tool=tool_name,
                    attempt=attempt + 1,
                    error=content[:500],
                )
                if attempt < MAX_RETRIES:
                    last_error = content
                    await asyncio.sleep(RETRY_DELAY)
                    continue

            if len(content) > MAX_CONTENT_LENGTH:
                content = content[:MAX_CONTENT_LENGTH] + "\n...(truncated)"

            return {
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": content,
                "is_error": is_error,
            }

        except Exception as exc:
            logger.warning(
                "tool call exception",
                server=server_key,
                tool=tool_name,
                attempt=attempt + 1,
                error=str(exc),
            )
            last_error = str(exc)
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY)
                continue
            raise

    return {
        "type": "tool_result",
        "tool_use_id": tool_use.id,
        "content": f"Error after {MAX_RETRIES + 1} attempts: {last_error}",
        "is_error": True,
    }


def _extract_content(content: Any) -> str:
    """Extract text from MCP tool result content."""
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for block in content:
        if hasattr(block, "text"):
            parts.append(block.text)
        else:
            parts.append(str(block))
    return "\n".join(parts)
