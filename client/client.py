import sys
import os
from pathlib import Path
from contextlib import asynccontextmanager

# Robust sys.path normalization on Windows
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CURRENT_DIR = os.path.normcase(os.path.abspath(os.path.dirname(__file__)))
sys.path = [p for p in sys.path if os.path.normcase(os.path.abspath(p)) != CURRENT_DIR]
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from dotenv import load_dotenv

load_dotenv()

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client
from client.llm.tools import convert_mcp_tools, MCPTool


@asynccontextmanager
async def connect_mcp(
    server_script: str = "server/server.py",
    server_url: str | None = None,
    transport: str | None = None,
):
    """
    Connects to the MCP database server over Streamable HTTP (default)
    or locally by spawning a subprocess over stdio.

    If server_url or MCP_SERVER_URL is provided, or if MCP_TRANSPORT is 'streamable-http',
    connects over Streamable HTTP (e.g. running locally or deployed on Render).
    Otherwise, if transport is 'stdio', spawns and connects locally over stdio.
    """
    if server_script and (server_script.startswith("http://") or server_script.startswith("https://")):
        server_url = server_script

    active_transport = (transport or os.getenv("MCP_TRANSPORT", "streamable-http")).lower()
    default_http_url = f"http://localhost:{os.getenv('PORT', os.getenv('MCP_PORT', '8000'))}{os.getenv('MCP_PATH', '/mcp')}"
    target_url = server_url or os.getenv("MCP_SERVER_URL") or (default_http_url if active_transport == "streamable-http" else None)

    if target_url and active_transport != "stdio":
        print(f"Connecting to MCP server over streamable-http at {target_url}...")
        async with streamable_http_client(url=target_url) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                print(f"Connected to MCP server at {target_url}.\n")

                response = await session.list_tools()
                tools = convert_mcp_tools(response.tools)
                print(f"Discovered {len(tools)} MCP tools: {[t.name for t in tools]}\n")

                yield session, tools
    else:
        server_params = StdioServerParameters(
            command="uv",
            args=["run", server_script, "--transport", "stdio"],
        )

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                print("Connected to local MCP server via stdio.\n")

                response = await session.list_tools()
                tools = convert_mcp_tools(response.tools)
                print(f"Discovered {len(tools)} MCP tools: {[t.name for t in tools]}\n")

                yield session, tools


if __name__ == "__main__":
    import asyncio
    from client.agent import main
    asyncio.run(main())
