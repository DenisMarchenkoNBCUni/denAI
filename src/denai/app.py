"""Entry point: python -m denai.app"""

import asyncio
import json
import logging
from pathlib import Path

import structlog

from denai.config import Settings
from denai.llm.orchestrator import Orchestrator
from denai.mcp.catalog import build_catalog
from denai.mcp.dispatch import init_jira_client
from denai.mcp.pool import McpPool
from denai.slack.bot import create_app

logger = structlog.get_logger()


async def main() -> None:
    settings = Settings()  # type: ignore[call-arg]
    log_level = logging.getLevelNamesMapping().get(settings.log_level.upper(), logging.INFO)
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
    )

    logger.info("starting denAI", model=settings.anthropic_model)

    # Initialize direct Jira client (bypasses broken mcp-atlassian search)
    config_path = Path(settings.mcp_config_path).expanduser()
    if config_path.exists():
        with open(config_path) as f:
            mcp_cfg = json.load(f)
        atlassian_env = mcp_cfg.get("mcpServers", {}).get("atlassian", {}).get("env", {})
        if atlassian_env.get("JIRA_URL"):
            init_jira_client(
                base_url=atlassian_env["JIRA_URL"],
                username=atlassian_env["JIRA_USERNAME"],
                api_token=atlassian_env["JIRA_API_TOKEN"],
            )
            logger.info("jira client initialized (direct REST)")

    # Connect to MCP servers
    pool = McpPool(settings)
    await pool.connect_all()

    # Build tool catalog
    catalog = await build_catalog(pool)
    logger.info("tool catalog built", tool_count=len(catalog))

    # Create orchestrator
    orchestrator = Orchestrator(settings=settings, pool=pool, catalog=catalog)

    # Start Slack bot
    app = create_app(settings=settings, orchestrator=orchestrator)
    await app.start_async()
    logger.info("socket mode connected")

    # Keep alive
    try:
        await asyncio.Event().wait()
    finally:
        await pool.close_all()


if __name__ == "__main__":
    asyncio.run(main())
