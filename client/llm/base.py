import os
import json
from dataclasses import dataclass
from typing import Any


def safe_json_loads(data: Any, fallback: Any = None) -> Any:
    """Safely parse a JSON string into a dict/list with fallback."""
    if isinstance(data, (dict, list)):
        return data
    if isinstance(data, str):
        try:
            return json.loads(data)
        except Exception:
            return fallback if fallback is not None else {"result": data}
    return fallback if fallback is not None else {"result": str(data)}


def clean_schema(schema: Any) -> Any:
    """Recursively remove schema fields (like additionalProperties) that unsupported by some LLMs."""
    if isinstance(schema, dict):
        return {
            key: clean_schema(value)
            for key, value in schema.items()
            if key != "additionalProperties"
        }
    if isinstance(schema, list):
        return [clean_schema(item) for item in schema]
    return schema


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]

    def to_openai_dict(self) -> dict[str, Any]:
        """Convert ToolCall to standard OpenAI/Groq function call schema."""
        args_str = (
            json.dumps(self.arguments)
            if isinstance(self.arguments, dict)
            else str(self.arguments)
        )
        return {
            "id": self.id or "call_0",
            "type": "function",
            "function": {
                "name": self.name,
                "arguments": args_str,
            },
        }


@dataclass
class LLMResponse:
    text: str | None
    tool_calls: list[ToolCall]
    raw: Any = None


class BaseLLM:

    def __init__(self, model: str):
        self.model = model

    @staticmethod
    def get_api_key(env_var: str) -> str:
        """Validate and retrieve an API key from environment variables."""
        key = os.getenv(env_var)
        if not key:
            raise ValueError(f"{env_var} is not set.")
        return key

    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[Any] | None = None,
    ) -> LLMResponse:
        raise NotImplementedError