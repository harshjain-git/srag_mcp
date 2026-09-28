import asyncio

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from client.llm.tools import convert_mcp_tools

async def main():
    server_params = StdioServerParameters(
        command="uv",
        args=["run", "server/server.py"],
    )

    async with stdio_client(server_params) as (read, write):

        async with ClientSession(read, write) as session:

            # Initialize the MCP connection
            await session.initialize()

            # print("Connected to MCP server.")
            # print()

            # Discover available tools
            response = await session.list_tools()

            mcp_tools = convert_mcp_tools(response.tools)

            
            from client.llm.factory import get_llm
            import os
            from dotenv import load_dotenv
            load_dotenv()

            provider = os.getenv("LLM_PROVIDER", "gemini")
            llm = get_llm(provider)

            llm_response = llm.generate(
                    messages=[
                    {
                        "role": "user",
                        "content": "Show me the first 3 employees from the database.",
                    }
                ],
                tools=mcp_tools,
            )

            print("\nLLM response:")
            print(llm_response)

            # print("\nConverted MCP tools:")

            # for tool in mcp_tools:
            #     print(f"\nName: {tool.name}")
            #     print(f"Description: {tool.description}")
            #     print(f"Input schema: {tool.input_schema}")

            # for tool in response.tools:
            #     print(f"- {tool.name}: {tool.description}")
            #     print(tool.input_schema)

            # result = await session.call_tool("schema", {})

            # print("\nDatabase schema:")
            # print(result)

            


if __name__ == "__main__":
    asyncio.run(main())

