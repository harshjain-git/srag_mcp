from typing import Any
from google import genai
from google.genai import types

from client.llm.base import BaseLLM, LLMResponse, ToolCall, clean_schema, safe_json_loads


class GeminiLLM(BaseLLM):

    def __init__(self, model: str):
        super().__init__(model)
        self.client = genai.Client(api_key=self.get_api_key("GEMINI_API_KEY"))

    def generate(self, messages: list[dict[str, Any]], tools=None) -> LLMResponse:
        contents, i = [], 0
        while i < len(messages):
            msg, role = messages[i], messages[i].get("role")

            if role == "user":
                contents.append(types.Content(role="user", parts=[types.Part.from_text(text=msg.get("content", ""))]))
                i += 1
            elif role in ("assistant", "model"):
                raw = msg.get("raw")
                content = (
                    raw.candidates[0].content
                    if (raw and hasattr(raw, "candidates") and raw.candidates)
                    else types.Content(role="model", parts=[types.Part.from_text(text=msg.get("content", ""))])
                )
                contents.append(content)
                i += 1
            elif role == "tool":
                tool_parts = []
                while i < len(messages) and messages[i].get("role") == "tool":
                    res = safe_json_loads(messages[i].get("content", ""), {"result": messages[i].get("content", "")})
                    tool_parts.append(
                        types.Part.from_function_response(
                            name=messages[i].get("name", ""),
                            response=res if isinstance(res, dict) else {"result": res},
                        )
                    )
                    i += 1
                contents.append(types.Content(role="user", parts=tool_parts))
            else:
                i += 1

        config = {}
        if tools:
            funcs = [
                types.FunctionDeclaration(name=t.name, description=t.description, parameters=clean_schema(t.input_schema))
                for t in tools
            ]
            config["tools"] = [types.Tool(function_declarations=funcs)]

        resp = self.client.models.generate_content(model=self.model, contents=contents, config=config)

        parts = resp.candidates[0].content.parts if (resp.candidates and resp.candidates[0].content) else []
        tool_calls = [
            ToolCall(id=p.function_call.id or "", name=p.function_call.name, arguments=dict(p.function_call.args or {}))
            for p in parts if p.function_call
        ]
        text = "".join(p.text for p in parts if p.text).strip() or None

        return LLMResponse(text=text, tool_calls=tool_calls, raw=resp)
