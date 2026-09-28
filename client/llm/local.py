from typing import Any

from ollama import Client

from client.llm.base import BaseLLM


class LocalLLM(BaseLLM):

    def __init__(
        self,
        model: str,
        host: str = "http://localhost:11434",
    ):
        self.client = Client(host=host)
        self.model = model

    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> Any:

        return self.client.chat(
            model=self.model,
            messages=messages,
            tools=tools or [],
        )

