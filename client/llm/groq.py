from typing import Any
from groq import Groq

from client.llm.base import BaseLLM, LLMResponse, ToolCall, clean_schema, safe_json_loads


class GroqLLM(BaseLLM):

    def __init__(self, model: str):
        super().__init__(model)
        self.client = Groq(api_key=self.get_api_key("GROQ_API_KEY"))

    def generate(self, messages: list[dict[str, Any]], tools=None) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": [self._format_msg(m) for m in messages],
        }
        if tools:
            kwargs["tools"] = [
                {"type": "function", "function": {"name": t.name, "description": t.description, "parameters": clean_schema(t.input_schema)}}
                for t in tools
            ]
            kwargs["tool_choice"] = "auto"

        resp = self.client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message

        tool_calls = [
            ToolCall(id=tc.id or "", name=tc.function.name, arguments=safe_json_loads(tc.function.arguments, fallback={}))
            for tc in (msg.tool_calls or [])
        ]
        return LLMResponse(text=msg.content, tool_calls=tool_calls, raw=resp)

    @staticmethod
    def _format_msg(msg: dict[str, Any]) -> dict[str, Any]:
        role = msg.get("role")
        if role in ("assistant", "model"):
            calls = [tc.to_openai_dict() if isinstance(tc, ToolCall) else tc for tc in msg.get("tool_calls", [])]
            return {"role": "assistant", "content": msg.get("content") or "", **({"tool_calls": calls} if calls else {})}
        if role == "tool":
            return {"role": "tool", "tool_call_id": msg.get("tool_call_id", "call_0"), "name": msg.get("name", ""), "content": str(msg.get("content", ""))}
        return {"role": role, "content": msg.get("content", "")}
