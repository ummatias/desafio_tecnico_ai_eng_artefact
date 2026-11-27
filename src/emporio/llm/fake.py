"""Cliente roteirizado para testes: devolve as respostas em ordem e grava cada requisição."""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from emporio.llm.types import LLMError, Message, Response, ToolCall, ToolSchema


@dataclass(frozen=True)
class RecordedRequest:
    messages: tuple[Message, ...]
    tools: tuple[ToolSchema, ...]


class FakeLLMClient:
    def __init__(self, script: Sequence[Response | LLMError]) -> None:
        self._script = list(script)
        self.requests: list[RecordedRequest] = []

    def complete(self, messages: Sequence[Message], tools: Sequence[ToolSchema]) -> Response:
        self.requests.append(RecordedRequest(tuple(messages), tuple(tools)))
        if not self._script:
            raise AssertionError(f"FakeLLMClient: roteiro esgotado na chamada {len(self.requests)}")
        step = self._script.pop(0)
        if isinstance(step, LLMError):
            raise step
        return step


def text_response(text: str) -> Response:
    return Response(text=text, finish_reason="stop")


def tool_call_response(
    name: str, arguments: Mapping[str, Any] | str, call_id: str = "call_1"
) -> Response:
    raw = arguments if isinstance(arguments, str) else json.dumps(arguments)
    return Response(
        text=None, tool_calls=(ToolCall(call_id, name, raw),), finish_reason="tool_calls"
    )
