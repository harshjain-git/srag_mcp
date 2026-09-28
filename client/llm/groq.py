import os
import json
from typing import Any

from groq import Groq

from client.llm.base import BaseLLM, LLMResponse, ToolCall


class GroqLLM(BaseLLM):

    def __init__(self, model: str):
        api_key = os.getenv("GROQ_API_KEY")

        if not api_key:
            raise ValueError(
                "GROQ_API_KEY is not set."
            )

        self.client = Groq(api_key=api_key)
        self.model = model

    def generate(
        self,
        messages: list[dict[str, Any]],
        tools= None,
    ) -> LLMResponse:

        groq_tools = self.convert_tools(tools) if tools else []

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=groq_tools,
            tool_choice="auto",
        )

        message = response.choices[0].message

        tool_calls = []

        if message.tool_calls:
            for tool_call in message.tool_calls:
                tool_calls.append(
                ToolCall(
                    id=tool_call.id,
                    name=tool_call.function.name,
                    arguments=__import__("json").loads(
                        tool_call.function.arguments
                    ),
                )
            )

        return LLMResponse(
            text=message.content,
            tool_calls=tool_calls,
            raw=response,
        )

    def convert_tools(self, tools):
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.input_schema,
                },
            }
            for tool in tools
        ]
