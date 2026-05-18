# denAI — Internal Slack AI Agent

> **Denis Marchenko hackathon project. This is temporal/experimental.**

denAI is an internal Slack bot that answers natural-language questions using Claude (Anthropic) with tool_use over multiple MCP (Model Context Protocol) servers.

Users `@denai <question>` in any Slack channel or DM and get answers from Jira, Confluence, DevDoc, GitHub, and Slack.

## Quick Start

```bash
# 1. Install dependencies
uv sync --extra dev

# 2. Configure .env (see .env.example)
cp .env.example .env

# 3. Run
uv run python -m denai.app
```

## Architecture

- **Slack** (Socket Mode via slack_bolt) → **Orchestrator** → **Claude** (tool_use loop) → **MCP Client Pool** → 4 MCP servers
- Per-thread in-memory conversation history
- Markdown → Slack mrkdwn formatting
- Prompt caching for cost efficiency

## MCP Servers

| Domain | MCP Server | Examples |
|--------|-----------|----------|
| Jira + Confluence | alexandria | "What's the status of RTS-1234?" |
| DevDoc | devdoc | "What's the logging pattern for k8s?" |
| GitHub | github | "Show open PRs in GolfNowEng/denAI" |
| Slack | slack | "What was discussed in #ops today?" |

## Tech Stack

- Python 3.12+, `uv` for package management
- `slack_bolt` (async, Socket Mode)
- `anthropic` SDK (Claude claude-sonnet-4-6)
- `mcp` Python SDK
- `pydantic-settings`, `structlog`, `ruff`, `pyright` (strict)

## Development

```bash
ruff check && ruff format --check
pyright
pytest -m "not integration"
```

## License

Internal use only.
