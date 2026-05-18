"""Convert standard Markdown to Slack mrkdwn format."""

import re


def markdown_to_mrkdwn(text: str) -> str:
    """Convert standard Markdown to Slack mrkdwn."""
    # Remove language identifier from code blocks
    text = re.sub(r"```\w+\n", "```\n", text)

    # Convert links [text](url) -> <url|text>
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"<\2|\1>", text)

    # Convert bold **text** -> *text*
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)

    # Convert italic *text* -> _text_ (but not inside bold)
    # Only match single * not preceded/followed by *
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"_\1_", text)

    # Convert headings to bold
    text = re.sub(r"^#{1,6}\s+(.+)$", r"*\1*", text, flags=re.MULTILINE)

    # Convert bullet lists
    text = re.sub(r"^[\-\*]\s+", "\u2022 ", text, flags=re.MULTILINE)

    return text
