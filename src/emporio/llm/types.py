"""
Tipos neutros entre o agente e o provedor de LLM.

O loop do agente só conhece estes tipos e o protocolo `LLMClient`
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

Role = Literal["system", "user", "assistant", "tool"]
ToolSchema = Mapping[str, Any]  # {"name", "description", "parameters"} de `tool_schemas()`


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str  # JSON cru do modelo


@dataclass(frozen=True)
class Message:
    role: Role
    content: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None
    # Raciocínio do modelo, reenviado sem interpretação nas mensagens do assistente
    reasoning: str | None = None
    reasoning_details: Any = None

    @classmethod
    def system(cls, content: str) -> "Message":
        return cls("system", content)

    @classmethod
    def user(cls, content: str) -> "Message":
        return cls("user", content)

    @classmethod
    def tool(cls, tool_call_id: str, content: str) -> "Message":
        return cls("tool", content, tool_call_id=tool_call_id)


@dataclass(frozen=True)
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    cached_tokens: int = 0
    cost_usd: float | None = None  # `usage.cost` do OpenRouter


@dataclass(frozen=True)
class Response:
    text: str | None
    tool_calls: tuple[ToolCall, ...] = ()
    usage: Usage = field(default_factory=Usage)
    finish_reason: str | None = None
    model: str | None = None
    provider: str | None = None  # quem serviu a chamada, quando a resposta informa
    generation_id: str | None = None
    latency_ms: float = 0.0
    reasoning: str | None = None
    reasoning_details: Any = None

    def as_message(self) -> Message:
        """A mensagem do assistente para o histórico, com o raciocínio para reenvio."""
        return Message(
            "assistant",
            self.text,
            tool_calls=self.tool_calls,
            reasoning=self.reasoning,
            reasoning_details=self.reasoning_details,
        )


class LLMClient(Protocol):
    def complete(self, messages: Sequence[Message], tools: Sequence[ToolSchema]) -> Response: ...


class LLMError(Exception):
    """Falha do LLM. O loop converte em resposta segura + escalada."""


class LLMConfigError(LLMError):
    """Configuração ausente ou inválida (ex.: sem `LLM_API_KEY`)."""


class LLMUnavailable(LLMError):
    """Falha transitória que persistiu depois dos retries."""


class LLMRejected(LLMError):
    """Requisição recusada (4xx): repetir não resolve."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class LLMTruncated(LLMError):
    """`finish_reason="length"` sem conteúdo: o raciocínio consumiu o limite de tokens."""
