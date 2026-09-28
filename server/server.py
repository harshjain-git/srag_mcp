import sys
from pathlib import Path

# Add project root directory to sys.path so 'server' package imports work cleanly
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from mcp.server import MCPServer
from server.tools.query_tool import execute_query
from server.tools.schema_tool import get_database_schema
from server.tools.create_tool import create_records
from server.tools.update_tool import update_records
from server.tools.delete_tool import delete_records

mcp = MCPServer("Structured RAG Database Server")

@mcp.tool()
def hello(name: str) -> str:
    """Say hello to a person."""
    return f"Hello, {name}!"

@mcp.tool()
def query(sql: str) -> list[dict]:
    """Execute a read-only SQL query."""
    return execute_query(sql)

@mcp.tool()
def schema() -> dict:
    """Return the current PostgreSQL database schema."""
    return get_database_schema()

@mcp.tool()
def create(
    operations: list[dict],
) -> list[dict]:
    """Create records across one or more existing database tables."""
    return create_records(operations)

@mcp.tool()
def update(
    operations: list[dict],
) -> list[dict]:
    """Update records across one or more existing database tables."""
    return update_records(operations)

@mcp.tool()
def delete(
    operations: list[dict],
) -> list[dict]:
    """Delete records from one or more existing database tables."""
    return delete_records(operations)

if __name__ == "__main__":
    print("Starting MCP server over stdio...", file=sys.stderr)
    mcp.run()
