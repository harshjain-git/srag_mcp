import os
import json
from typing import Any

from google import genai

from client.llm.base import BaseLLM, LLMResponse, ToolCall
from google.genai import types


class GeminiLLM(BaseLLM):

    def __init__(self, model: str):
        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY is not set."
            )

        self.client = genai.Client(api_key=api_key)
        self.model = model

    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> Any:

        contents = []

        for message in messages:
            contents.append(
                f"{message['role']}: {message['content']}"
            )

        prompt = "\n".join(contents)

        config = {}

        if tools:
            function_declarations = self.convert_tools(tools)
            config["tools"] = [
                types.Tool(
                    function_declarations=function_declarations
                )
            ]

        return self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=config,
        )

        print("\nRAW GEMINI RESPONSE:")
        print(response)
        return(response)

    def convert_tools(self, tools):
        return [
            types.FunctionDeclaration(
                name=tool.name,
                description=tool.description,
                parameters=self.clean_schema(tool.input_schema),
            )
            for tool in tools
        ]


    @staticmethod
    def clean_schema(schema):
        """
        Remove JSON Schema fields that Gemini does not support.
        """

        if isinstance(schema, dict):
            return {
                key: GeminiLLM.clean_schema(value)
                for key, value in schema.items()
                if key != "additionalProperties"
            }

        if isinstance(schema, list):
            return [GeminiLLM.clean_schema(item)
                for item in schema]

        return schema
