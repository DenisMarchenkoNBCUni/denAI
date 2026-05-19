"""MCP client pool — one session per server, supports stdio and HTTP transports."""

import contextlib
import json
from pathlib import Path
from typing import Any

import httpx
import structlog
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import get_default_environment, stdio_client
from mcp.client.streamable_http import streamable_http_client

from denai.config import Settings

logger = structlog.get_logger()


class McpPool:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self.sessions: dict[str, ClientSession] = {}
        self._transports: list[Any] = []  # keep references to prevent GC

    def _load_mcp_config(self) -> dict[str, Any]:
        """Load MCP server definitions from the host config file and project configs."""
        config_path = Path(self._settings.mcp_config_path).expanduser()
        servers: dict[str, Any] = {}

        # Load from main settings.json
        if config_path.exists():
            with open(config_path) as f:
                config = json.load(f)
            servers.update(config.get("mcpServers", {}))

        # Load from project-level .mcp.json
        local_mcp = Path(".mcp.json")
        if local_mcp.exists():
            with open(local_mcp) as f:
                data = json.load(f)
            servers.update(data.get("mcpServers", {}))

        return servers

    async def connect_all(self) -> None:
        """Connect to all configured MCP servers."""
        mcp_config = self._load_mcp_config()

        for server_key in self._settings.mcp_servers:
            if server_key not in mcp_config:
                logger.warning("MCP server not in config, skipping", server=server_key)
                continue

            server_def = mcp_config[server_key]
            try:
                await self._connect_server(server_key, server_def)
            except Exception as exc:
                logger.error("failed to connect MCP server", server=server_key, error=str(exc))

    async def _connect_server(self, key: str, server_def: dict[str, Any]) -> None:
        """Connect to a single MCP server via stdio or HTTP."""
        server_type = server_def.get("type", "stdio")

        if server_type == "http":
            await self._connect_http(key, server_def)
        else:
            await self._connect_stdio(key, server_def)

    async def _connect_http(self, key: str, server_def: dict[str, Any]) -> None:
        """Connect to an MCP server over HTTP (streamable-http)."""
        url = server_def["url"]
        headers = server_def.get("headers", {})

        http_client = httpx.AsyncClient(headers=headers, timeout=30.0)
        transport = streamable_http_client(url=url, http_client=http_client)
        read, write, _ = await transport.__aenter__()
        self._transports.append(transport)

        session = ClientSession(read, write)
        await session.__aenter__()
        await session.initialize()

        tools = await session.list_tools()
        tool_count = len(tools.tools) if tools.tools else 0

        self.sessions[key] = session
        logger.info("connected MCP server (HTTP)", server=key, tools=tool_count, url=url)

    async def _connect_stdio(self, key: str, server_def: dict[str, Any]) -> None:
        """Connect to a single MCP server via stdio."""
        command = server_def.get("command", "")
        args = server_def.get("args", [])
        env_override = server_def.get("env")

        env = get_default_environment()
        if env_override:
            env.update(env_override)

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
        logger.info("connected MCP server (stdio)", server=key, tools=tool_count)

    async def close_all(self) -> None:
        """Close all MCP sessions."""
        for key, session in self.sessions.items():
            try:
                await session.__aexit__(None, None, None)
            except Exception:
                logger.warning("error closing MCP session", server=key)

        for transport in self._transports:
            with contextlib.suppress(Exception):
                await transport.__aexit__(None, None, None)
