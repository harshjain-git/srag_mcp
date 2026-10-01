"""A2A (Agent-to-Agent) protocol routes for Structured RAG."""

from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.request_handlers.response_helpers import agent_card_to_dict
from a2a.server.routes.jsonrpc_dispatcher import JsonRpcDispatcher
from a2a.server.tasks import InMemoryTaskStore
from starlette.requests import Request
from starlette.responses import JSONResponse

from a2a_server import SRAGAgentExecutor, get_srag_agent_card, srag_agent_card


def register_a2a_routes(mcp) -> None:
    """Register A2A Agent Card and JSON-RPC endpoints directly on an MCPServer instance."""
    in_process_executor = SRAGAgentExecutor(mcp_server=mcp)
    handler = DefaultRequestHandler(
        agent_executor=in_process_executor,
        task_store=InMemoryTaskStore(),
        agent_card=srag_agent_card,
    )
    dispatcher = JsonRpcDispatcher(
        request_handler=handler,
        enable_v0_3_compat=True,
    )

    @mcp.custom_route("/.well-known/agent-card.json", methods=["GET"])
    async def agent_card_endpoint(request: Request) -> JSONResponse:
        """Serve dynamic A2A Agent Card based on incoming request host / URL."""
        base_url = str(request.base_url).rstrip("/")
        card = get_srag_agent_card(base_url)
        return JSONResponse(agent_card_to_dict(card))

    @mcp.custom_route("/", methods=["POST"])
    @mcp.custom_route("/a2a", methods=["POST"])
    async def a2a_endpoint(request: Request):
        """Dispatch incoming A2A JSON-RPC requests to the database agent executor."""
        return await dispatcher.handle_requests(request)
