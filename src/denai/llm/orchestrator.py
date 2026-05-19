"""LLM orchestrator with tool-use loop."""

import asyncio
from typing import Any

import structlog
from anthropic import AsyncAnthropic

from denai.config import Settings
from denai.errors import ToolIterationLimitExceeded, UnexpectedStopReason
from denai.mcp.dispatch import dispatch
from denai.mcp.pool import McpPool

logger = structlog.get_logger()

MAX_TOOL_ITERATIONS = 8

SYSTEM_PROMPT = """You are denAI, an internal Slack assistant for the engineering team.

You have tools across multiple MCP servers:
- github__*: GitHub PRs, issues, commits, code search, and reviews.
- atlassian__*: Jira tickets, Confluence pages, search, and comments.
- keystone__*: Internal skill/agent/chain search and retrieval.
- mssql__*: Query SQL Server databases, list tables, describe schemas, run queries.

Rules:
- Answer the question directly, then stop. Do not add follow-up questions or commentary.
- Never assume a message was "cut off" or incomplete. Treat every message as complete.
- Pick the smallest tool call that can answer the question.
- Chain tools when needed.
- When you cite a PR, issue, or page, include the URL.
- Format answers for Slack: use *bold*, _italic_, `code`, > blockquote, and bulleted lists.
  NO Markdown headings (#), NO tables.
- Keep answers concise — no filler, no emojis unless the user uses them first.
- If a tool errors, surface the error message verbatim to the user and stop.

Jira tips:
- For ANY Jira search/query, use the atlassian__jira_search_jql tool. Do NOT use search_jira_issues (it's broken).
- For "my tickets" or "assigned to me", use JQL: assignee = "{email}" where {email} is the requesting user's email from the context below. NEVER use currentUser() — it resolves to the service account, not the person asking.
- Include status filter (e.g., status != Done) unless the user asks for completed tickets.
- For reading a single issue by key, use atlassian__read_jira_issue with issueKey parameter.
"""


class Orchestrator:
    def __init__(self, settings: Settings, pool: McpPool, catalog: list[dict[str, Any]]) -> None:
        self._settings = settings
        self._pool = pool
        self._catalog = catalog
        self._client = AsyncAnthropic(
            auth_token=settings.anthropic_api_key,
            base_url=settings.anthropic_base_url,
        )
        self.last_messages: list[dict[str, Any]] = []

    def _catalog_with_cache_control(self) -> list[dict[str, Any]]:
        """Add cache_control to the last tool for prompt caching."""
        if not self._catalog:
            return []
        tools = [dict(t) for t in self._catalog]
        tools[-1]["cache_control"] = {"type": "ephemeral"}
        return tools

    @staticmethod
    def _trim_history(messages: list[dict[str, Any]], max_turns: int) -> list[dict[str, Any]]:
        """Trim history to max_turns without orphaning tool_result blocks."""
        if len(messages) <= max_turns:
            return messages
        trimmed = messages[-max_turns:]
        # If first message is a tool_result (user role with tool_result content),
        # drop it and the preceding assistant tool_use (if present) to avoid orphans.
        while trimmed:
            first = trimmed[0]
            content = first.get("content")
            is_tool_result = (
                first.get("role") == "user"
                and isinstance(content, list)
                and any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content)
            )
            if is_tool_result:
                trimmed = trimmed[1:]
            else:
                break
        # Also drop a leading assistant message with tool_use (orphaned without its result)
        while trimmed:
            first = trimmed[0]
            content = first.get("content")
            has_tool_use = first.get("role") == "assistant" and isinstance(content, list) and any(
                (hasattr(b, "type") and b.type == "tool_use")
                or (isinstance(b, dict) and b.get("type") == "tool_use")
                for b in content
            )
            if has_tool_use:
                trimmed = trimmed[1:]
            else:
                break
        return trimmed

    async def answer(
        self, question: str, thread_history: list[dict[str, Any]], user_context: str = ""
    ) -> str:
        messages: list[dict[str, Any]] = [*thread_history, {"role": "user", "content": question}]

        system_text = SYSTEM_PROMPT
        if user_context:
            system_text += f"\n\nRequesting user context:\n{user_context}"

        for iteration in range(MAX_TOOL_ITERATIONS):
            logger.debug("calling claude", iteration=iteration, message_count=len(messages))

            resp = await self._client.messages.create(
                model=self._settings.anthropic_model,
                max_tokens=self._settings.anthropic_max_tokens,
                system=[
                    {
                        "type": "text",
                        "text": system_text,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                tools=self._catalog_with_cache_control(),  # type: ignore[arg-type]
                messages=messages,  # type: ignore[arg-type]
            )

            if resp.stop_reason == "end_turn":
                messages.append({"role": "assistant", "content": resp.content})
                self.last_messages = self._trim_history(
                    messages, self._settings.history_max_turns
                )
                return self._extract_text(resp.content)

            if resp.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": resp.content})
                tool_uses = [b for b in resp.content if b.type == "tool_use"]

                logger.info("tool calls", tools=[t.name for t in tool_uses])

                results = await asyncio.gather(
                    *(dispatch(self._pool, t) for t in tool_uses),
                    return_exceptions=True,
                )

                tool_results: list[dict[str, Any]] = []
                for tu, result in zip(tool_uses, results, strict=True):
                    if isinstance(result, BaseException):
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": tu.id,
                                "content": f"Error: {result}",
                                "is_error": True,
                            }
                        )
                    else:
                        tool_results.append(result)

                messages.append({"role": "user", "content": tool_results})
                continue

            raise UnexpectedStopReason(resp.stop_reason or "unknown")

        raise ToolIterationLimitExceeded(MAX_TOOL_ITERATIONS)

    @staticmethod
    def _extract_text(content: Any) -> str:
        """Extract text from Claude response content blocks."""
        parts: list[str] = []
        for block in content:
            if hasattr(block, "text"):
                parts.append(block.text)
        return "\n".join(parts) if parts else "(no response)"
