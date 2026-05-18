"""Tests for Slack formatting."""

from denai.slack.formatting import markdown_to_mrkdwn


def test_bold_conversion() -> None:
    assert markdown_to_mrkdwn("**hello**") == "*hello*"


def test_link_conversion() -> None:
    assert markdown_to_mrkdwn("[click](http://example.com)") == "<http://example.com|click>"


def test_heading_to_bold() -> None:
    assert markdown_to_mrkdwn("# Title") == "*Title*"
    assert markdown_to_mrkdwn("## Subtitle") == "*Subtitle*"


def test_code_block_strips_language() -> None:
    text = "```python\nprint('hi')\n```"
    result = markdown_to_mrkdwn(text)
    assert "python" not in result
    assert "print('hi')" in result


def test_bullet_list() -> None:
    result = markdown_to_mrkdwn("- item one\n- item two")
    assert "\u2022 item one" in result
    assert "\u2022 item two" in result
