import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Robust sys.path normalization on Windows:
# Remove the script directory from sys.path so 'client.py' doesn't shadow the 'client' package
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CURRENT_DIR = os.path.normcase(os.path.abspath(os.path.dirname(__file__)))

sys.path = [
    p for p in sys.path
    if os.path.normcase(os.path.abspath(p)) != CURRENT_DIR
]
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Evict shadowed 'client' module if already cached as a file
if "client" in sys.modules and not hasattr(sys.modules["client"], "__path__"):
    del sys.modules["client"]

# Configure UTF-8 on Windows terminal to support Unicode characters
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from mcp import ClientSession
from client.client import connect_mcp
from client.llm.base import BaseLLM, ToolCall
from client.llm.factory import get_llm
from client.llm.tools import MCPTool

load_dotenv()


TOOL_OPERATION_TYPES = {
    "schema": "Inspection (R - Read)",
    "query": "Query Execution (R - Read)",
    "create": "Record Creation (C - Create)",
    "update": "Record Update (U - Update)",
    "delete": "Record Deletion (D - Delete)",
}


async def execute_tool(session: ClientSession, tool_call: ToolCall) -> str:
    """Execute a single MCP tool call and print structured operation details."""
    op_type = TOOL_OPERATION_TYPES.get(tool_call.name, "Custom (C/R/U/D)")
    print(f"Tool Used            : {tool_call.name}")
    print(f"Tool Operation (CRUD): {op_type}")

    if "sql" in tool_call.arguments:
        print(f"SQL Generated        : {tool_call.arguments['sql']}")
    elif "operations" in tool_call.arguments:
        print(f"Operations Payload   : {tool_call.arguments['operations']}")
    elif tool_call.arguments:
        print(f"Arguments            : {tool_call.arguments}")

    tool_result = await session.call_tool(
        tool_call.name,
        tool_call.arguments,
    )

    result_text = "\n".join(
        part.text
        for part in tool_result.content
        if hasattr(part, "text")
    )

    preview = result_text[:250] + ("..." if len(result_text) > 250 else "")
    print(f"Tool Result ({tool_call.name}) :\n{preview}\n")

    return result_text


async def run_agent(
    session: ClientSession,
    llm: BaseLLM,
    tools: list[MCPTool],
    query: str,
    max_turns: int = 10,
) -> str | None:
    """
    Run the sequential agent reasoning loop with structured CLI logging:
    1. Print User Query
    2. Display tool executions with SQL and CRUD classifications
    3. Output Final Answer and Total Tools summary
    """
    print(f"User Query           : {query}\n")

    messages: list[dict] = [
        {"role": "user", "content": query}
    ]
    tools_used_history: list[str] = []

    for turn in range(1, max_turns + 1):
        print(f"--- Turn {turn} ---")

        # Step 1: Query LLM with conversation history and available tools
        llm_response = llm.generate(messages=messages, tools=tools)

        # Step 2: Check if LLM reached the final answer
        if not llm_response.tool_calls:
            print("=" * 65)
            print("Final Answer:")
            print(llm_response.text)
            print("=" * 65)
            total_summary = ", ".join(tools_used_history) if tools_used_history else "None"
            print(f"Total Tools Used     : {total_summary} ({len(tools_used_history)} calls total)\n")
            return llm_response.text

        # Step 3: Record model turn (preserving raw candidate metadata for Gemini)
        messages.append({
            "role": "assistant",
            "content": llm_response.text,
            "tool_calls": llm_response.tool_calls,
            "raw": llm_response.raw,
        })

        # Step 4: Execute requested tool calls against the MCP server
        for tool_call in llm_response.tool_calls:
            tools_used_history.append(tool_call.name)
            result_text = await execute_tool(session, tool_call)

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": tool_call.name,
                "content": result_text,
            })

    print("Reached maximum turns without a final answer.")
    return None


async def main():
    """Run the agent with an MCP connection in interactive CLI mode."""
    async with connect_mcp() as (session, tools):
        provider = os.getenv("LLM_PROVIDER", "gemini")
        llm = get_llm(provider)

        print(f"Active Provider: {provider.upper()} ({llm.model})")

        # 1. Direct one-shot query via command line: uv run client/agent.py "query"
        if len(sys.argv) > 1:
            query = " ".join(sys.argv[1:])
            await run_agent(session, llm, tools, query)
            return

        # 2. Continuous interactive terminal session
        print("=" * 65)
        print("Interactive Database Assistant (type 'exit', 'quit', or 'q' to stop)")
        print("=" * 65)

        while True:
            try:
                query = input("\nAsk DB > ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nExiting session. Goodbye!")
                break

            if not query:
                continue

            if query.lower() in ("exit", "quit", "q"):
                print("Goodbye!")
                break

            print()
            await run_agent(session, llm, tools, query)

if __name__ == "__main__":
    asyncio.run(main())
