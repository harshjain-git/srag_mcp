"""Web UI and internal HTTP API routes for Structured RAG."""

from pathlib import Path
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse

from client.agent import run_agent
from server.tools.schema_tool import get_database_schema

INDEX_HTML_PATH = Path(__file__).resolve().parent.parent / "web" / "index.html"


def register_web_routes(mcp) -> None:
    """Register Web Chat UI, health check, and internal API routes on the MCPServer."""

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
