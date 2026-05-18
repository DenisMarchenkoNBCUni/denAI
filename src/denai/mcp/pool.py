"""MCP client pool — one session per server."""

import json
from pathlib import Path
from typing import Any

import structlog
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from denai.config import Settings

logger = structlog.get_logger()


class McpPool:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self.sessions: dict[str, ClientSession] = {}
        self._transports: list[Any] = []  # keep references to prevent GC

    def _load_mcp_config(self) -> dict[str, Any]:
        """Load MCP server definitions from the host config file."""
        config_path = Path(self._settings.mcp_config_path).expanduser()
        if not config_path.exists():
            raise FileNotFoundError(f"MCP config not found: {config_path}")

        with open(config_path) as f:
            config = json.load(f)

        # Support both top-level 'mcpServers' and nested structures
        servers = config.get("mcpServers", config.get("mcp_servers", {}))
        return servers  # type: ignore[no-any-return]

    async def connect_all(self) -> None:
        """Connect to all configured MCP servers."""
        mcp_config = self._load_mcp_config()

        for server_key in self._settings.mcp_servers:
            if server_key not in mcp_config:
                logger.warning("MCP server not in config, skipping", server=server_key)
                continue

            server_def = mcp_config[server_key]
            await self._connect_server(server_key, server_def)

    async def _connect_server(self, key: str, server_def: dict[str, Any]) -> None:
        """Connect to a single MCP server via stdio."""
        command = server_def.get("command", "")
        args = server_def.get("args", [])
        env = server_def.get("env", None)

        params = StdioServerParameters(command=command, args=args, env=env)

        transport = stdio_client(params)
        read, write = await transport.__aenter__()
        self._transports.append(transport)

        session = ClientSession(read, write)
        await session.__aenter__()
        await session.initialize()

        tools = await session.list_tools()
        tool_count = len(tools.tools) if tools.tools else 0

        self.sessions[key] = session
        logger.info("connected MCP server", server=key, tools=tool_count)

    async def close_all(self) -> None:
        """Close all MCP sessions."""
        for key, session in self.sessions.items():
            try:
                await session.__aexit__(None, None, None)
            except Exception:
                logger.warning("error closing MCP session", server=key)

        for transport in self._transports:
            try:
                await transport.__aexit__(None, None, None)
            except Exception:
                pass
