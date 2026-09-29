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

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from client.llm.tools import convert_mcp_tools, MCPTool


@asynccontextmanager
async def connect_mcp(server_script: str = "server/server.py"):
    """
    Spawns and connects to the MCP database server over stdio.
    Yields:
        (session, tools): Active ClientSession and list of discovered MCPTool objects.
    """
    server_params = StdioServerParameters(
        command="uv",
        args=["run", server_script],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize connection & discover available database tools
            await session.initialize()
            print("Connected to MCP server.\n")

            response = await session.list_tools()
            tools = convert_mcp_tools(response.tools)
            print(f"Discovered {len(tools)} MCP tools: {[t.name for t in tools]}\n")

            yield session, tools


if __name__ == "__main__":
    import asyncio
    from client.agent import main
    asyncio.run(main())
