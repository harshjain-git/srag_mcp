import argparse
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse

# Add project root directory to sys.path so 'server' package imports work cleanly
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

load_dotenv()

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from client.agent import run_agent
from server.tools.query_tool import execute_query
from server.tools.schema_tool import get_database_schema
from server.tools.create_tool import create_records
from server.tools.update_tool import update_records
from server.tools.delete_tool import delete_records

mcp = MCPServer("Structured RAG Database Server")

INDEX_HTML_PATH = Path(__file__).resolve().parent / "web" / "index.html"


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    """Health check endpoint for Render zero-downtime deploys and uptime monitoring."""
    return JSONResponse({"status": "healthy", "service": "srag-mcp-server"})


@mcp.custom_route("/", methods=["GET"])
@mcp.custom_route("/chat", methods=["GET"])
@mcp.custom_route("/chat/", methods=["GET"])
async def index_endpoint(request: Request) -> HTMLResponse:
    """Serve the Web Chat UI."""
    if INDEX_HTML_PATH.exists():
        return HTMLResponse(INDEX_HTML_PATH.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Structured RAG MCP Server</h1><p>Web UI not found. MCP endpoint active at /mcp</p>")


@mcp.custom_route("/api/chat", methods=["POST"])
async def chat_endpoint(request: Request) -> JSONResponse:
    """Execute natural-language database query through agent reasoning loop."""
    try:
        payload = await request.json()
        query_text = payload.get("query", "").strip()
        if not query_text:
            return JSONResponse({"success": False, "error": "Query cannot be empty."}, status_code=400)

        history = payload.get("history", [])
        provider = payload.get("provider")

        result = await run_agent(
            mcp_target=mcp,
            query=query_text,
            history=history,
            provider=provider,
            verbose=False,
            return_details=True,
        )
        return JSONResponse(result)
    except Exception as exc:
        return JSONResponse({"success": False, "error": str(exc)}, status_code=500)


@mcp.custom_route("/api/schema", methods=["GET"])
async def schema_endpoint(request: Request) -> JSONResponse:
    """Return database schema as JSON for UI inspector modal."""
    try:
        return JSONResponse(get_database_schema())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@mcp.tool()
def query(sql: str) -> list[dict]:
    """Execute a read-only SQL query against the database."""
    try:
        return execute_query(sql)
    except Exception as e:
        raise ToolError(f"Query error: {e}")

@mcp.tool()
def schema() -> dict:
    """Return the current PostgreSQL database schema including tables, columns, and foreign keys."""
    try:
        return get_database_schema()
    except Exception as e:
        raise ToolError(f"Schema error: {e}")

@mcp.tool()
def create(
    operations: list[dict],
) -> list[dict]:
    """
    Insert records into existing database tables.
    Each operation must be a dict with:
      - 'table': str (e.g. 'departments')
      - 'records': list[dict] (e.g. [{'department_id': 6, 'department_name': 'Operations', 'location': 'Delhi'}])
    """
    try:
        return create_records(operations)
    except Exception as e:
        raise ToolError(f"Create error: {e}")

@mcp.tool()
def update(
    operations: list[dict],
) -> list[dict]:
    """
    Update records across existing database tables.
    Each operation must be a dict with:
      - 'table': str (e.g. 'departments')
      - 'updates': dict (e.g. {'department_name': 'New Name'})
      - 'where': dict (e.g. {'department_id': 7})
    """
    try:
        return update_records(operations)
    except Exception as e:
        raise ToolError(f"Update error: {e}")

@mcp.tool()
def delete(
    operations: list[dict],
) -> list[dict]:
    """
    Delete records from existing database tables.
    Each operation must be a dict with:
      - 'table': str (e.g. 'departments')
      - 'where': dict (e.g. {'department_id': 8})
    """
    try:
        return delete_records(operations)
    except Exception as e:
        raise ToolError(f"Delete error: {e}")

if __name__ == "__main__":
    # Render automatically sets RENDER=true and assigns the PORT environment variable
    is_render = os.getenv("RENDER", "").lower() == "true"
    default_transport = "streamable-http" if is_render else "stdio"

    parser = argparse.ArgumentParser(description="Structured RAG MCP Database Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http", "sse"],
        default=os.getenv("MCP_TRANSPORT", default_transport),
        help="Transport type (stdio, streamable-http, sse)",
    )
    parser.add_argument(
        "--host",
        default=os.getenv("HOST", os.getenv("MCP_HOST", "0.0.0.0")),
        help="Host address to bind HTTP server to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("PORT", os.getenv("MCP_PORT", "8000"))),
        help="Port number to bind HTTP server to (default: PORT env or 8000)",
    )
    parser.add_argument(
        "--path",
        default=os.getenv("MCP_PATH", "/mcp"),
        help="Streamable HTTP endpoint path (default: /mcp)",
    )

    args = parser.parse_args()

    if args.transport == "streamable-http":
        display_host = "localhost" if args.host in ("0.0.0.0", "::") else args.host
        print(
            f"\n"
            f"===============================================================\n"
            f"  Structured RAG MCP Server (Streamable HTTP)\n"
            f"  -> Web Chat UI : http://{display_host}:{args.port}/\n"
            f"  -> MCP Endpoint: http://{display_host}:{args.port}{args.path}\n"
            f"  -> Health Check: http://{display_host}:{args.port}/health\n"
            f"===============================================================\n",
            file=sys.stderr,
        )
        mcp.run(
            transport="streamable-http",
            host=args.host,
            port=args.port,
            streamable_http_path=args.path,
        )
    elif args.transport == "sse":
        print(f"Starting MCP server over SSE on http://{args.host}:{args.port} ...", file=sys.stderr)
        mcp.run(transport="sse", host=args.host, port=args.port)
    else:
        print("Starting MCP server over stdio...", file=sys.stderr)
        mcp.run(transport="stdio")
