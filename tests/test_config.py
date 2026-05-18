"""Tests for configuration."""

import os
from unittest.mock import patch

import pytest

from denai.config import Settings


def test_settings_loads_from_env() -> None:
    env = {
        "AI_SLACK_BOT_TOKEN": "xoxb-test",
        "AI_SLACK_APP_TOKEN": "xapp-test",
        "AI_ANTHROPIC_API_KEY": "sk-ant-test",
    }
    with patch.dict(os.environ, env, clear=False):
        s = Settings()  # type: ignore[call-arg]
        assert s.slack_bot_token == "xoxb-test"
        assert s.anthropic_model == "claude-sonnet-4-6"
        assert s.history_max_turns == 20


def test_settings_missing_required_raises() -> None:
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(Exception):
            Settings()  # type: ignore[call-arg]
