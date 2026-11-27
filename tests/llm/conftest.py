"""Servidor falso do OpenRouter: o SDK real conversa com um `httpx2.MockTransport`."""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx2
import pytest

from emporio.config import Settings
from emporio.llm.openrouter import OpenRouterClient

Reply = tuple[int, dict[str, Any], dict[str, str]] | Exception


def settings(**overrides: Any) -> Settings:
    return Settings(_env_file=None, llm_api_key="sk-or-test", **overrides)


def ok_body(
    content: str | None = "Olá!",
    *,
    tool_calls: list[dict[str, Any]] | None = None,
    finish_reason: str = "stop",
    provider: str | None = "DeepInfra",
    reasoning: str | None = None,
    reasoning_details: Any = None,
) -> dict[str, Any]:
    message: dict[str, Any] = {"role": "assistant", "content": content}
    if tool_calls is not None:
        message["tool_calls"] = tool_calls
    if reasoning is not None:
        message["reasoning"] = reasoning
    if reasoning_details is not None:
        message["reasoning_details"] = reasoning_details
    body: dict[str, Any] = {
        "id": "gen-123",
        "model": "openai/gpt-oss-120b",
        "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
        "usage": {
            "prompt_tokens": 900,
            "completion_tokens": 120,
            "total_tokens": 1020,
            "cost": 0.000321,
            "prompt_tokens_details": {"cached_tokens": 512},
            "completion_tokens_details": {"reasoning_tokens": 80},
        },
    }
    if provider is not None:
        body["provider"] = provider
    return body


def error_body(status: int, message: str, error_type: str | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": status, "message": message}
    if error_type is not None:
        error["metadata"] = {"error_type": error_type}
    return {"error": error}


@dataclass
class FakeServer:
    replies: list[Reply]
    requests: list[httpx2.Request] = field(default_factory=list)

    def handler(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        status, body, headers = reply
        return httpx2.Response(status, json=body, headers=headers)

    def bodies(self) -> list[dict[str, Any]]:
        return [json.loads(r.content) for r in self.requests]


@dataclass
class Harness:
    server: FakeServer
    client: OpenRouterClient
    sleeps: list[float]


MakeHarness = Callable[..., Harness]


@pytest.fixture
def harness() -> MakeHarness:
    def make(*replies: Reply, **overrides: Any) -> Harness:
        server = FakeServer(list(replies))
        sleeps: list[float] = []
        client = OpenRouterClient(
            settings(**overrides),
            http_client=httpx2.Client(transport=httpx2.MockTransport(server.handler)),
            sleep=sleeps.append,
            jitter=lambda: 1.0,
        )
        return Harness(server, client, sleeps)

    return make


def ok(body: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Reply:
    return (200, body or ok_body(), headers or {})
