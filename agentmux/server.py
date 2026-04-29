"""agentmux MCP server entrypoint.

Wires the :class:`SessionRegistry` and :class:`ToolDispatcher` to the
``mcp`` SDK's stdio server. Run via the ``agentmux`` console script
(see ``pyproject.toml``) or ``python -m agentmux.server``.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from agentmux.session import SessionRegistry
from agentmux.tools import ToolDispatcher, tool_definitions

log = logging.getLogger("agentmux")


def _configure_logging() -> None:
    level_name = os.environ.get("AGENTMUX_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    # IMPORTANT: log to stderr so we never corrupt the stdio MCP channel.
    logging.basicConfig(
        level=level,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def build_server() -> tuple[Server, SessionRegistry]:
    """Construct the MCP server and its dependencies."""
    registry = SessionRegistry()
    dispatcher = ToolDispatcher(registry)
    server: Server = Server("agentmux")

    @server.list_tools()
    async def _list_tools() -> list[Tool]:
        return [
            Tool(
                name=t["name"],
                description=t["description"],
                inputSchema=t["inputSchema"],
            )
            for t in tool_definitions()
        ]

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict | None) -> list[TextContent]:
        try:
            result = await dispatcher.call(name, arguments or {})
        except Exception as e:  # noqa: BLE001
            log.exception("Tool %s failed", name)
            return [TextContent(type="text", text=f"ERROR: {type(e).__name__}: {e}")]
        return [TextContent(type="text", text=result)]

    return server, registry


async def run() -> None:
    _configure_logging()
    server, registry = build_server()
    log.info("agentmux starting (pid=%d)", os.getpid())
    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )
    finally:
        log.info("agentmux shutting down — killing %d sessions", len(registry.list()))
        await registry.shutdown()


def main() -> None:
    """Console-script entrypoint."""
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
