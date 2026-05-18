"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="AI_")

    # Slack
    slack_bot_token: str
    slack_app_token: str

    # Anthropic (via Keystone proxy)
    anthropic_api_key: str
    anthropic_base_url: str = "https://golfnow-keystone.vdpv.ai"
    anthropic_model: str = "claude-sonnet-4-6"
    anthropic_max_tokens: int = 4096

    # MCP
    mcp_config_path: str = "~/.claude/settings.json"
    mcp_servers: list[str] = ["github", "atlassian", "slack", "keystone"]

    # Behaviour
    history_max_turns: int = 20
    log_level: str = "INFO"
