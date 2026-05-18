"""Slack bot using slack_bolt async with Socket Mode."""

# pyright: reportUnusedFunction=false

import contextlib
from typing import Any

import structlog
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp

from denai.config import Settings
from denai.llm.orchestrator import Orchestrator
from denai.slack.formatting import markdown_to_mrkdwn
from denai.slack.memory import ThreadMemory

logger = structlog.get_logger()


def create_app(settings: Settings, orchestrator: Orchestrator) -> AsyncSocketModeHandler:
    app = AsyncApp(token=settings.slack_bot_token)
    memory = ThreadMemory(max_turns=settings.history_max_turns)

    @app.event("app_mention")  # type: ignore[misc]
    async def handle_mention(event: dict[str, Any], say: Any, client: Any) -> None:
        channel = event["channel"]
        thread_ts = event.get("thread_ts") or event["ts"]
        text = event.get("text", "")
        user = event.get("user", "")

        if event.get("bot_id"):
            return

        with contextlib.suppress(Exception):
            await client.reactions_add(
                channel=channel, timestamp=event["ts"], name="eyes"
            )

        question = text.split(">", 1)[-1].strip() if ">" in text else text

        logger.info("received mention", user=user, channel=channel, question=question[:100])

        try:
            history = memory.get(channel, thread_ts)
            answer = await orchestrator.answer(question=question, thread_history=history)
            memory.set(channel, thread_ts, orchestrator.last_messages)

            formatted = markdown_to_mrkdwn(answer)
            await say(text=formatted, thread_ts=thread_ts)

            with contextlib.suppress(Exception):
                await client.reactions_remove(
                    channel=channel, timestamp=event["ts"], name="eyes"
                )
                await client.reactions_add(
                    channel=channel, timestamp=event["ts"], name="white_check_mark"
                )

        except Exception as exc:
            logger.exception("error handling mention", error=str(exc))
            await say(
                text=f"⚠️ Sorry, I hit an error: {exc}",
                thread_ts=thread_ts,
            )
            with contextlib.suppress(Exception):
                await client.reactions_remove(
                    channel=channel, timestamp=event["ts"], name="eyes"
                )

    @app.event("message")  # type: ignore[misc]
    async def handle_dm(event: dict[str, Any], say: Any, client: Any) -> None:
        if event.get("channel_type") != "im":
            return
        if event.get("bot_id") or event.get("subtype"):
            return

        channel = event["channel"]
        text = event.get("text", "")

        logger.info("received DM", channel=channel, question=text[:100])

        with contextlib.suppress(Exception):
            await client.reactions_add(
                channel=channel, timestamp=event["ts"], name="eyes"
            )

        try:
            history = memory.get(channel, None)
            answer = await orchestrator.answer(question=text, thread_history=history)
            memory.set(channel, None, orchestrator.last_messages)

            formatted = markdown_to_mrkdwn(answer)
            await say(text=formatted, channel=channel)

            with contextlib.suppress(Exception):
                await client.reactions_remove(
                    channel=channel, timestamp=event["ts"], name="eyes"
                )
                await client.reactions_add(
                    channel=channel, timestamp=event["ts"], name="white_check_mark"
                )

        except Exception as exc:
            logger.exception("error handling DM", error=str(exc))
            await say(text=f"⚠️ Sorry, I hit an error: {exc}", channel=channel)

    handler = AsyncSocketModeHandler(app, settings.slack_app_token)
    return handler
