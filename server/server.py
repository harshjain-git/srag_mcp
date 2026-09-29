import sys
from pathlib import Path

# Add project root directory to sys.path so 'server' package imports work cleanly
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from server.tools.query_tool import execute_query
from server.tools.schema_tool import get_database_schema
from server.tools.create_tool import create_records
from server.tools.update_tool import update_records
from server.tools.delete_tool import delete_records

mcp = MCPServer("Structured RAG Database Server")


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
    print("Starting MCP server over stdio...", file=sys.stderr)
    mcp.run()
