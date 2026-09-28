import os

from client.llm.base import BaseLLM
from client.llm.gemini import GeminiLLM
from client.llm.groq import GroqLLM
from client.llm.local import LocalLLM


def get_llm(
    provider: str | None = None,
) -> BaseLLM:

    provider = (
        provider
        or os.getenv("LLM_PROVIDER", "gemini")
    ).lower()

    if provider == "gemini":
        model = os.getenv(
            "GEMINI_MODEL",
            "gemini-3.1-flash-lite-preview",
        )

        return GeminiLLM(model)

    if provider == "groq":
        model = os.getenv(
            "GROQ_MODEL",
            "openai/gpt-oss-120b",
        )

        return GroqLLM(model)

    if provider in {"local", "llama", "ollama"}:
        model = os.getenv(
            "LOCAL_MODEL",
            "llama3.1",
        )

        return LocalLLM(model)

    raise ValueError(
        f"Unsupported LLM provider: {provider}"
    )

