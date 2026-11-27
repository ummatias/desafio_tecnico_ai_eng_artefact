"""LLM atrás do protocolo `LLMClient`; OpenRouter por padrão."""

from emporio.config import Settings
from emporio.llm.types import (
    LLMClient,
    LLMConfigError,
    LLMError,
    LLMRejected,
    LLMTruncated,
    LLMUnavailable,
    Message,
    Response,
    ToolCall,
    ToolSchema,
    Usage,
)


def make_llm_client(settings: Settings) -> LLMClient:
    from emporio.llm.openrouter import OpenRouterClient

    return OpenRouterClient(settings)


__all__ = [
    "LLMClient",
    "LLMConfigError",
    "LLMError",
    "LLMRejected",
    "LLMTruncated",
    "LLMUnavailable",
    "Message",
    "Response",
    "ToolCall",
    "ToolSchema",
    "Usage",
    "make_llm_client",
]
