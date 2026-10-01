import asyncio
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from dotenv import load_dotenv

# Ensure srag_mcp root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Configure UTF-8 on Windows terminal
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

load_dotenv()

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import (
    create_agent_card_routes,
    create_jsonrpc_routes,
    create_rest_routes,
)
from a2a.server.tasks import InMemoryTaskStore
from a2a.helpers import new_text_message
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
)

from client.agent import run_agent
from client.client import connect_mcp
from client.llm.factory import get_llm


# A2A AgentSkill defining the SRAG agent's PostgreSQL capabilities via MCP
srag_skill = AgentSkill(
    id="srag_postgres_agent",
    name="Structured RAG PostgreSQL Agent",
    description=(
        "Executes structured data operations and analytics against a PostgreSQL database "
        "via the Model Context Protocol (MCP). Capabilities include inspecting table schemas, "
        "generating and executing read-only SQL queries from natural language, and performing "
        "structured CRUD (create, read, update, delete) operations across relational tables."
    ),
    tags=[
        "postgresql",
        "sql",
        "database",
        "structured-data",
        "mcp",
        "crud",
        "schema-inspection",
        "srag",
    ],
    examples=[
        "What is the schema of the database?",
        "List all departments in the organization.",
        "How many employees are currently hired?",
        "Find all active projects and their assigned departments.",
        "Insert a new department named 'Operations' in 'Delhi'.",
    ],
    input_modes=["text/plain"],
    output_modes=["text/plain"],
)


# A2A AgentCard definition for the SRAG agent
A2A_HOST = os.getenv("A2A_HOST", "localhost")
A2A_PORT = int(os.getenv("A2A_PORT", "8001"))
AGENT_URL = os.getenv("A2A_AGENT_URL", f"http://{A2A_HOST}:{A2A_PORT}")

srag_agent_card = AgentCard(
    name="Structured RAG PostgreSQL Agent",
    description=(
        "Structured Retrieval-Augmented Generation (SRAG) agent that interacts with "
        "a PostgreSQL database via the Model Context Protocol (MCP) to perform schema "
        "inspection, analytical SQL querying, and CRUD operations."
    ),
    version="1.0.0",
    supported_interfaces=[
        AgentInterface(
            url=AGENT_URL,
            protocol_binding="JSONRPC",
            protocol_version="1.0",
        ),
        AgentInterface(
            url=AGENT_URL,
            protocol_binding="REST",
            protocol_version="1.0",
        ),
    ],
    capabilities=AgentCapabilities(
        streaming=False,
        push_notifications=False,
    ),
    default_input_modes=["text/plain"],
    default_output_modes=["text/plain"],
    skills=[srag_skill],
)


class SRAGAgentExecutor(AgentExecutor):
    """A2A AgentExecutor wrapper around the SRAG reasoning agent.

    Receives tasks/questions over the A2A protocol and delegates them
    to the SRAG agent which accesses PostgreSQL via MCP.
    """

    def __init__(self, server_script: str | None = None):
        super().__init__()
        self._server_script = server_script or str(PROJECT_ROOT / "server" / "server.py")
        self._session = None
        self._tools = None
        self._lock = asyncio.Lock()

    def set_mcp(self, session, tools):
        """Set active MCP session and tools for persistent lifecycle reuse."""
        self._session = session
        self._tools = tools

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Process incoming user task/query from A2A and return the SRAG agent response."""
        user_query = context.get_user_input()
        print(f"\n[A2A Server] Received query: {user_query}")

        if not user_query.strip():
            reply = new_text_message(
                text="No question or task was provided.",
                context_id=context.context_id,
                task_id=context.task_id,
            )
            await event_queue.enqueue_event(reply)
            return

        async with self._lock:
            # Reuse lifespan MCP session if available; fallback to per-request connection
            if self._session and self._tools:
                provider = os.getenv("LLM_PROVIDER", "gemini")
                llm = get_llm(provider)
                answer = await run_agent(self._session, llm, self._tools, user_query)
            else:
                async with connect_mcp(self._server_script) as (session, tools):
                    provider = os.getenv("LLM_PROVIDER", "gemini")
                    llm = get_llm(provider)
                    answer = await run_agent(session, llm, tools, user_query)

        if not answer:
            answer = "No response was generated or the agent reached maximum turns without a final answer."

        reply = new_text_message(
            text=answer,
            context_id=context.context_id,
            task_id=context.task_id,
        )
        await event_queue.enqueue_event(reply)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Handle cancellation requests."""
        print(f"[A2A Server] Task {context.task_id} cancellation requested.")


# Initialize executor and A2A request handler with srag_agent_card
executor = SRAGAgentExecutor()
task_store = InMemoryTaskStore()
request_handler = DefaultRequestHandler(
    agent_executor=executor,
    task_store=task_store,
    agent_card=srag_agent_card,
)


async def health_check(request):
    """Simple health check endpoint."""
    return JSONResponse({
        "status": "healthy",
        "service": "srag-a2a-server",
        "protocol": "A2A v1.0",
    })


routes = [
    Route("/health", health_check, methods=["GET"]),
    *create_agent_card_routes(agent_card=srag_agent_card),
    *create_jsonrpc_routes(request_handler=request_handler, rpc_url="/", enable_v0_3_compat=True),
    *create_rest_routes(request_handler=request_handler, enable_v0_3_compat=True),
]


@asynccontextmanager
async def lifespan(app: Starlette):
    """Manage lifecycle: connect to MCP server on startup and close on shutdown."""
    server_script = str(PROJECT_ROOT / "server" / "server.py")
    print("[A2A Server] Spawning and connecting to MCP database server...")
    async with connect_mcp(server_script=server_script) as (session, tools):
        executor.set_mcp(session, tools)
        print("[A2A Server] MCP server connected and ready.")
        yield
    print("[A2A Server] MCP server session closed.")


# Expose Starlette ASGI application
app = Starlette(routes=routes, lifespan=lifespan)


def main():
    """Run the A2A server using uvicorn."""
    import uvicorn
    host = os.getenv("A2A_HOST", "0.0.0.0")
    port = int(os.getenv("A2A_PORT", "8001"))
    print(f"Starting A2A Server on http://{host}:{port}...")
    uvicorn.run("a2a_server:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
