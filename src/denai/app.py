"""Entry point: python -m denai.app"""

import asyncio

import structlog

from denai.config import Settings
from denai.llm.orchestrator import Orchestrator
from denai.mcp.catalog import build_catalog
from denai.mcp.pool import McpPool
from denai.slack.bot import create_app

logger = structlog.get_logger()


async def main() -> None:
    settings = Settings()  # type: ignore[call-arg]
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(
            structlog.get_level_from_name(settings.log_level)  # type: ignore[arg-type]
        ),
    )

    logger.info("starting denAI", model=settings.anthropic_model)

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
