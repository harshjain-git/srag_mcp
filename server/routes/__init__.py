"""Route registration package for Structured RAG server."""

from server.routes.web_routes import register_web_routes
from server.routes.a2a_routes import register_a2a_routes


def register_all_routes(mcp) -> None:
    """Register both Web UI / Chat endpoints and A2A protocol endpoints on the MCPServer."""
    register_web_routes(mcp)
    register_a2a_routes(mcp)


__all__ = ["register_all_routes", "register_web_routes", "register_a2a_routes"]
