import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any
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

from client.client import connect_mcp
from client.llm.base import BaseLLM, ToolCall
from client.llm.factory import get_llm
from client.llm.tools import convert_mcp_tools, MCPTool

load_dotenv()


TOOL_OPERATION_TYPES = {
    "schema": "Inspection (R - Read)",
    "query": "Query Execution (R - Read)",
    "create": "Record Creation (C - Create)",
    "update": "Record Update (U - Update)",
    "delete": "Record Deletion (D - Delete)",
}


async def execute_tool(
    mcp_target: Any,
    tool_call: ToolCall,
    verbose: bool = True,
) -> str:
    """
    Execute a single MCP tool call against an MCPServer (in-process)
    or ClientSession (stdio/network).
    """
    op_type = TOOL_OPERATION_TYPES.get(tool_call.name, "Custom (C/R/U/D)")
    if verbose:
        print(f"Tool Used            : {tool_call.name}")
        print(f"Tool Operation (CRUD): {op_type}")
        if "sql" in tool_call.arguments:
            print(f"SQL Generated        : {tool_call.arguments['sql']}")
        elif "operations" in tool_call.arguments:
            print(f"Operations Payload   : {tool_call.arguments['operations']}")
        elif tool_call.arguments:
            print(f"Arguments            : {tool_call.arguments}")

    tool_result = await mcp_target.call_tool(
        tool_call.name,
        tool_call.arguments,
    )

    result_text = "\n".join(
        part.text
        for part in tool_result.content
        if hasattr(part, "text")
    )

    if verbose:
        preview = result_text[:250] + ("..." if len(result_text) > 250 else "")
        print(f"Tool Result ({tool_call.name}) :\n{preview}\n")

    return result_text


async def run_agent(
    mcp_target: Any,
    llm: BaseLLM | None = None,
    tools: list[MCPTool] | None = None,
    query: str | None = None,
    *,
    history: list[dict[str, str]] | None = None,
    provider: str | None = None,
    max_turns: int = 10,
    verbose: bool = True,
    return_details: bool = False,
) -> Any:
    """
    Unified agent runner for both CLI and Web/API execution.

    Parameters:
      - mcp_target: MCPServer instance or ClientSession
      - llm: Optional BaseLLM instance (resolved via provider if None)
      - tools: Optional list of converted MCPTool objects (discovered if None)
      - query: The user's query prompt
      - history: Optional prior conversation turns
      - provider: Optional LLM provider name ('gemini', 'groq', 'ollama')
      - max_turns: Maximum reasoning turns before cutoff (default: 10)
      - verbose: Print formatted logs to stdout (default: True)
      - return_details: If True, returns a rich dictionary with steps, sql, and tabular data;
                        if False, returns string answer or None for CLI/A2A compatibility.
    """
    # Allow flexible calling styles: run_agent(target, "query") or run_agent(target, llm, tools, "query")
    if isinstance(llm, str) and query is None:
        query = llm
        llm = None

    if query is None:
        raise ValueError("query is required for run_agent")

    steps: list[dict[str, Any]] = []
    captured_sql: str | None = None
    tabular_data: list[dict[str, Any]] | None = None

    try:
        if llm is None:
            provider = provider or os.getenv("LLM_PROVIDER", "gemini")
            llm = get_llm(provider)
        else:
            provider = provider or getattr(llm, "provider", None) or os.getenv("LLM_PROVIDER", "gemini")

        if tools is None:
            raw_tools = await mcp_target.list_tools()
            tools_list = getattr(raw_tools, "tools", raw_tools)
            tools = convert_mcp_tools(tools_list)

        if verbose:
            print(f"User Query           : {query}\n")

        SYSTEM_INSTRUCTION = (
            "You are a helpful, knowledgeable AI database assistant connected to PostgreSQL via MCP.\n"
            "Guidelines for formatting your response:\n"
            "1. Respond in natural, conversational, and friendly English.\n"
            "2. When organizing your answer into sections, use standard clean Markdown headings (e.g. '### Database Schema' or '### Department Records'). Never prefix headings with solitary asterisks like '* Heading' or '*Heading*'.\n"
            "3. When presenting lists or records, use natural single bullet points with each item on its own separate line:\n"
            "   - **Item Name**: Description or details\n"
            "   Never use double bullets or nested bullets.\n"
            "4. DO NOT output raw ASCII pipe-separated tables (such as | Col1 | Col2 |) in your text response. Provide clean, natural prose.\n"
            "5. Keep the formatting clean, elegant, and easy to read."
        )

        # Build initial message history
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_INSTRUCTION}
        ]
        if history:
            for item in history[-6:]:
                role = item.get("role", "user")
                if role in ("user", "assistant"):
                    messages.append({"role": role, "content": item.get("content", "")})

        messages.append({"role": "user", "content": query})

        tools_used_history: list[str] = []

        for turn in range(1, max_turns + 1):
            if verbose:
                print(f"--- Turn {turn} ---")

            llm_response = llm.generate(messages=messages, tools=tools)

            if not llm_response.tool_calls:
                answer = llm_response.text or "I completed the request."
                if verbose:
                    print("=" * 65)
                    print("Final Answer:")
                    print(answer)
                    print("=" * 65)
                    total_summary = ", ".join(tools_used_history) if tools_used_history else "None"
                    print(f"Total Tools Used     : {total_summary} ({len(tools_used_history)} calls total)\n")

                if return_details:
                    return {
                        "success": True,
                        "answer": answer,
                        "steps": steps,
                        "sql": captured_sql,
                        "data": tabular_data,
                        "provider": provider,
                        "model": getattr(llm, "model", str(llm)),
                    }
                return answer

            messages.append({
                "role": "assistant",
                "content": llm_response.text,
                "tool_calls": llm_response.tool_calls,
                "raw": llm_response.raw,
            })

            for tool_call in llm_response.tool_calls:
                tools_used_history.append(tool_call.name)
                result_text = await execute_tool(mcp_target, tool_call, verbose=verbose)

                # Parse JSON output (handles single JSON, arrays, and concatenated multi-record JSON)
                parsed_records: list[dict[str, Any]] = []
                try:
                    loaded = json.loads(result_text)
                    if isinstance(loaded, list):
                        parsed_records = [r for r in loaded if isinstance(r, dict)]
                    elif isinstance(loaded, dict):
                        if "records" in loaded and isinstance(loaded["records"], list):
                            parsed_records = [r for r in loaded["records"] if isinstance(r, dict)]
                        elif not any(isinstance(v, (dict, list)) for v in loaded.values()):
                            parsed_records = [loaded]
                except Exception:
                    # Stream of multiple JSON objects separated by whitespace/newlines
                    try:
                        decoder = json.JSONDecoder()
                        idx = 0
                        raw_str = result_text.strip()
                        while idx < len(raw_str):
                            while idx < len(raw_str) and raw_str[idx].isspace():
                                idx += 1
                            if idx >= len(raw_str):
                                break
                            obj, next_idx = decoder.raw_decode(raw_str, idx)
                            if isinstance(obj, dict):
                                parsed_records.append(obj)
                            elif isinstance(obj, list):
                                parsed_records.extend([r for r in obj if isinstance(r, dict)])
                            idx = next_idx
                    except Exception:
                        pass

                # Only save tabular_data for SQL queries returning flat row records (never schema metadata)
                if tool_call.name == "query" and parsed_records:
                    flat_records = [
                        r for r in parsed_records
                        if isinstance(r, dict) and not any(isinstance(v, (dict, list)) for v in r.values())
                    ]
                    if flat_records:
                        tabular_data = flat_records

                if "sql" in tool_call.arguments:
                    captured_sql = tool_call.arguments["sql"]

                steps.append({
                    "turn": turn,
                    "tool": tool_call.name,
                    "arguments": tool_call.arguments,
                    "sql": tool_call.arguments.get("sql"),
                    "result_preview": result_text[:400] + ("..." if len(result_text) > 400 else ""),
                    "is_tabular": bool(parsed_records),
                })

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_call.name,
                    "content": result_text,
                })

        if verbose:
            print("Reached maximum turns without a final answer.")

        if return_details:
            return {
                "success": True,
                "answer": "Reached maximum reasoning turns without a final response.",
                "steps": steps,
                "sql": captured_sql,
                "data": tabular_data,
                "provider": provider,
                "model": getattr(llm, "model", str(llm)),
            }
        return None

    except Exception as exc:
        if verbose:
            print(f"Error during agent execution: {exc}")
        if return_details:
            return {
                "success": False,
                "answer": f"An error occurred while processing your request: {exc}",
                "error": str(exc),
                "steps": steps,
                "sql": captured_sql,
                "data": tabular_data,
            }
        raise


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
