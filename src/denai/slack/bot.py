"""Slack bot using slack_bolt async with Socket Mode."""

import structlog
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

from denai.config import Settings
from denai.llm.orchestrator import Orchestrator
from denai.slack.formatting import markdown_to_mrkdwn
from denai.slack.memory import ThreadMemory

logger = structlog.get_logger()


def create_app(settings: Settings, orchestrator: Orchestrator) -> AsyncSocketModeHandler:
    app = AsyncApp(token=settings.slack_bot_token)
    memory = ThreadMemory(max_turns=settings.history_max_turns)

    @app.event("app_mention")
    async def handle_mention(event: dict, say, client) -> None:  # type: ignore[no-untyped-def]
        channel = event["channel"]
        thread_ts = event.get("thread_ts") or event["ts"]
        text = event.get("text", "")
        user = event.get("user", "")

        # Ignore bots
        if event.get("bot_id"):
            return

        # Add thinking reaction
        try:
            await client.reactions_add(channel=channel, timestamp=event["ts"], name="eyes")
        except Exception:
            pass

        # Strip the bot mention from the text
        # Text comes as "<@BOTID> actual question"
        question = text.split(">", 1)[-1].strip() if ">" in text else text

        logger.info("received mention", user=user, channel=channel, question=question[:100])

        try:
            history = memory.get(channel, thread_ts)
            answer = await orchestrator.answer(question=question, thread_history=history)
            memory.set(channel, thread_ts, orchestrator.last_messages)

            formatted = markdown_to_mrkdwn(answer)
            await say(text=formatted, thread_ts=thread_ts)

            # Swap reaction
            try:
                await client.reactions_remove(channel=channel, timestamp=event["ts"], name="eyes")
                await client.reactions_add(channel=channel, timestamp=event["ts"], name="white_check_mark")
            except Exception:
                pass

        except Exception as exc:
            logger.exception("error handling mention", error=str(exc))
            await say(
                text=f"\u26a0\ufe0f Sorry, I hit an error: {exc}",
                thread_ts=thread_ts,
            )
            try:
                await client.reactions_remove(channel=channel, timestamp=event["ts"], name="eyes")
            except Exception:
                pass

    @app.event("message")
    async def handle_dm(event: dict, say, client) -> None:  # type: ignore[no-untyped-def]
        # Only handle DMs (channel type 'im')
        if event.get("channel_type") != "im":
            return
        if event.get("bot_id") or event.get("subtype"):
            return

        channel = event["channel"]
        text = event.get("text", "")

        logger.info("received DM", channel=channel, question=text[:100])

        try:
            await client.reactions_add(channel=channel, timestamp=event["ts"], name="eyes")
        except Exception:
            pass

        try:
            history = memory.get(channel, None)
            answer = await orchestrator.answer(question=text, thread_history=history)
            memory.set(channel, None, orchestrator.last_messages)

            formatted = markdown_to_mrkdwn(answer)
            await say(text=formatted, channel=channel)

            try:
                await client.reactions_remove(channel=channel, timestamp=event["ts"], name="eyes")
                await client.reactions_add(channel=channel, timestamp=event["ts"], name="white_check_mark")
            except Exception:
                pass

        except Exception as exc:
            logger.exception("error handling DM", error=str(exc))
            await say(text=f"\u26a0\ufe0f Sorry, I hit an error: {exc}", channel=channel)

    handler = AsyncSocketModeHandler(app, settings.slack_app_token)
    return handler
