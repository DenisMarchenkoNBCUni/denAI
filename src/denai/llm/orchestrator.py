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
- keystone__*: Internal skill/agent/chain search and retrieval.

Rules:
- Pick the smallest tool call that can answer the question.
- Chain tools when needed.
- If a question is ambiguous, ask one clarifying question instead of guessing.
- When you cite a PR, issue, or page, include the URL.
- Format answers for Slack: use *bold*, _italic_, `code`, > blockquote, and bulleted lists.
  NO Markdown headings (#), NO tables.
- Keep answers concise.
- If a tool errors, surface the error message verbatim to the user and stop.
"""


class Orchestrator:
    def __init__(self, settings: Settings, pool: McpPool, catalog: list[dict[str, Any]]) -> None:
        self._settings = settings
        self._pool = pool
        self._catalog = catalog
        self._client = AsyncAnthropic(
            api_key=settings.anthropic_api_key,
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

    async def answer(self, question: str, thread_history: list[dict[str, Any]]) -> str:
        messages: list[dict[str, Any]] = [*thread_history, {"role": "user", "content": question}]

        for iteration in range(MAX_TOOL_ITERATIONS):
            logger.debug("calling claude", iteration=iteration, message_count=len(messages))

            resp = await self._client.messages.create(
                model=self._settings.anthropic_model,
                max_tokens=self._settings.anthropic_max_tokens,
                system=[
                    {
                        "type": "text",
                        "text": SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                tools=self._catalog_with_cache_control(),  # type: ignore[arg-type]
                messages=messages,  # type: ignore[arg-type]
            )

            if resp.stop_reason == "end_turn":
                messages.append({"role": "assistant", "content": resp.content})
                self.last_messages = messages[-self._settings.history_max_turns :]
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
