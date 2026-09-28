from dataclasses import dataclass
from typing import Any


@dataclass
class MCPTool:
    name: str
    description: str
    input_schema: dict[str, Any]


def convert_mcp_tools(mcp_tools) -> list[MCPTool]:
    """
    Convert MCP tool definitions into a provider-neutral format.
    """

    return [
        MCPTool(
            name=tool.name,
            description=tool.description or "",
            input_schema=tool.input_schema,
        )
        for tool in mcp_tools
    ]