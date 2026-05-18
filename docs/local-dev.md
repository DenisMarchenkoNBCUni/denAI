# Local Development

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Slack workspace with admin access to install apps
- Anthropic API key
- MCP servers configured locally (via Claude Code or similar)

## Setup

1. Clone the repo:
```bash
git clone https://github.com/DenisMarchenkoNBCUni/denAI.git
cd denAI
```

2. Install dependencies:
```bash
uv sync --extra dev
```

3. Create your `.env` file:
```bash
cp .env.example .env
# Edit .env with your actual tokens
```

4. Create the Slack app:
   - Go to https://api.slack.com/apps
   - Click "Create New App" → "From manifest"
   - Paste contents of `docs/slack-app-manifest.yaml`
   - Install to workspace
   - Copy Bot Token (`xoxb-...`) → `AI_SLACK_BOT_TOKEN`
   - Generate App-Level Token with `connections:write` → `AI_SLACK_APP_TOKEN`

5. Run:
```bash
uv run python -m denai.app
```

## Testing

```bash
uv run pytest -m "not integration"
uv run ruff check
uv run pyright
```
