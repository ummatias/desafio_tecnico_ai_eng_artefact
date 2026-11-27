"""
Adaptador do OpenRouter (API compatível com OpenAI) atrás do `LLMClient`.

- Retries próprios: 408, 429, 5xx, timeout, falha de conexão e erro transitório dentro de
  um HTTP 200 (o OpenRouter devolve `error` no corpo ou `finish_reason="error"`). Respeita o
  `Retry-After`, senão, backoff exponencial com jitter. O SDK fica com `max_retries=0`.
- Sem retry em 4xx: repetir não resolve. O 404 acontece quando nenhum provider atende a rota.
- Custo de `usage.cost`, provider e id da geração gravados quando vierem
- Raciocínio do modelo reenviado nas mensagens do assistente.
"""

import random
import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import httpx2
from openai import APIConnectionError, APIStatusError, OpenAI

from emporio.config import Settings
from emporio.llm.schemas import openai_tools
from emporio.llm.types import (
    LLMConfigError,
    LLMRejected,
    LLMTruncated,
    LLMUnavailable,
    Message,
    Response,
    ToolCall,
    ToolSchema,
    Usage,
)

TRANSIENT_STATUS = frozenset({408, 429, 500, 502, 503, 504})
TRANSIENT_ERROR_TYPES = frozenset(
    {"rate_limit_exceeded", "provider_overloaded", "provider_unavailable", "timeout", "server"}
)
BACKOFF_BASE_SECONDS = 1.0
MAX_WAIT_SECONDS = 30.0


class _Transient(Exception):
    def __init__(self, reason: str, retry_after: float | None = None) -> None:
        super().__init__(reason)
        self.retry_after = retry_after


def _retry_after(headers: Mapping[str, str]) -> float | None:
    value = headers.get("retry-after")
    try:
        return max(0.0, float(value)) if value is not None else None
    except ValueError:
        return None


def _payload_message(m: Message) -> dict[str, Any]:
    out: dict[str, Any] = {"role": m.role, "content": m.content}
    if m.role == "tool":
        out["tool_call_id"] = m.tool_call_id
    if m.role == "assistant":
        if m.tool_calls:
            out["tool_calls"] = [
                {
                    "id": c.id,
                    "type": "function",
                    "function": {"name": c.name, "arguments": c.arguments},
                }
                for c in m.tool_calls
            ]
        if m.reasoning_details is not None:
            out["reasoning_details"] = m.reasoning_details
        elif m.reasoning is not None:
            out["reasoning"] = m.reasoning
    return out


def _body_error(body: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """Erro dentro de um HTTP 200: `error` no topo ou em `choices[0]`."""
    if isinstance(body.get("error"), Mapping):
        error: Mapping[str, Any] = body["error"]
        return error
    choices = body.get("choices") or []
    if choices and choices[0].get("finish_reason") == "error":
        choice_error = choices[0].get("error")
        return (
            choice_error
            if isinstance(choice_error, Mapping)
            else {"message": "finish_reason=error"}
        )
    return None


def _error_type(error: Mapping[str, Any]) -> str | None:
    metadata = error.get("metadata")
    if isinstance(metadata, Mapping) and isinstance(metadata.get("error_type"), str):
        return str(metadata["error_type"])
    value = error.get("type") or error.get("error_type")
    return str(value) if value is not None else None


def _usage(raw: Any) -> Usage:
    if not isinstance(raw, Mapping):
        return Usage()
    prompt_details = raw.get("prompt_tokens_details") or {}
    completion_details = raw.get("completion_tokens_details") or {}
    cost = raw.get("cost")
    return Usage(
        prompt_tokens=int(raw.get("prompt_tokens") or 0),
        completion_tokens=int(raw.get("completion_tokens") or 0),
        reasoning_tokens=int(completion_details.get("reasoning_tokens") or 0),
        cached_tokens=int(prompt_details.get("cached_tokens") or 0),
        cost_usd=float(cost) if cost is not None else None,
    )


def parse_response(body: Mapping[str, Any], latency_ms: float) -> Response:
    choices = body.get("choices") or []
    if not choices:
        raise LLMUnavailable("resposta sem choices")
    choice = choices[0]
    message = choice.get("message") or {}
    tool_calls = tuple(
        ToolCall(
            id=str(call.get("id") or f"call_{i}"),
            name=str(call["function"]["name"]),
            arguments=str(call["function"].get("arguments") or ""),
        )
        for i, call in enumerate(message.get("tool_calls") or [])
    )
    text = message.get("content") or None
    finish_reason = choice.get("finish_reason")
    if finish_reason == "length" and not text and not tool_calls:
        raise LLMTruncated("limite de tokens atingido sem resposta (LLM_MAX_TOKENS)")
    return Response(
        text=text,
        tool_calls=tool_calls,
        usage=_usage(body.get("usage")),
        finish_reason=finish_reason,
        model=body.get("model"),
        provider=body.get("provider"),
        generation_id=body.get("id"),
        latency_ms=latency_ms,
        reasoning=message.get("reasoning") or message.get("reasoning_content"),
        reasoning_details=message.get("reasoning_details"),
    )


class OpenRouterClient:
    def __init__(
        self,
        settings: Settings,
        *,
        http_client: httpx2.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        jitter: Callable[[], float] = random.random,
    ) -> None:
        if settings.llm_api_key is None:
            raise LLMConfigError("LLM_API_KEY não definida: configure a chave do OpenRouter")
        self._settings = settings
        self._sleep = sleep
        self._jitter = jitter
        self._client = OpenAI(
            api_key=settings.llm_api_key.get_secret_value(),
            base_url=settings.llm_base_url,
            timeout=settings.llm_timeout_seconds,
            max_retries=0,
            http_client=http_client,
        )

    def _extra_body(self) -> dict[str, Any]:
        s = self._settings
        provider: dict[str, Any] = {
            "data_collection": s.llm_data_collection,
            "require_parameters": True,  # só providers que aceitam tools
        }
        if s.llm_provider_order:
            provider["order"] = s.llm_provider_order
            provider["allow_fallbacks"] = False
        extra: dict[str, Any] = {"provider": provider}
        if s.llm_reasoning_effort is not None:
            extra["reasoning"] = {"effort": s.llm_reasoning_effort}
        return extra

    def _wait(self, attempt: int, retry_after: float | None) -> None:
        if retry_after is not None:
            delay = retry_after
        else:
            delay = BACKOFF_BASE_SECONDS * 2**attempt * (0.5 + self._jitter() / 2)
        self._sleep(min(delay, MAX_WAIT_SECONDS))

    def _rejected(self, exc: APIStatusError) -> LLMRejected:
        if exc.status_code == 404:
            return LLMRejected(
                "nenhum provider atende a requisição (404). Com LLM_DATA_COLLECTION=deny e tools, "
                "pode não haver provider disponível para o modelo; revise LLM_DATA_COLLECTION "
                f"e LLM_PROVIDERS. Detalhe: {exc.message}",
                status=404,
            )
        return LLMRejected(
            f"requisição recusada ({exc.status_code}): {exc.message}", exc.status_code
        )

    def _call(self, kwargs: Mapping[str, Any]) -> Response:
        start = time.perf_counter()
        try:
            raw = self._client.chat.completions.with_raw_response.create(**kwargs)
        except APIStatusError as exc:
            retry_after = _retry_after(exc.response.headers)
            if exc.status_code in TRANSIENT_STATUS or (exc.status_code == 402 and retry_after):
                raise _Transient(f"HTTP {exc.status_code}", retry_after) from exc
            raise self._rejected(exc) from exc
        except APIConnectionError as exc:  # inclui timeout
            raise _Transient(type(exc).__name__) from exc
        latency_ms = (time.perf_counter() - start) * 1000
        body = raw.http_response.json()
        if not isinstance(body, Mapping):
            raise LLMUnavailable("resposta não é um objeto JSON")
        error = _body_error(body)
        if error is not None:
            if _error_type(error) in TRANSIENT_ERROR_TYPES:
                raise _Transient(f"erro no corpo: {_error_type(error)}")
            raise LLMUnavailable(f"erro do provider: {error.get('message', error)}")
        return parse_response(body, latency_ms)

    def complete(self, messages: Sequence[Message], tools: Sequence[ToolSchema]) -> Response:
        kwargs: dict[str, Any] = {
            "model": self._settings.llm_model,
            "messages": [_payload_message(m) for m in messages],
            "max_tokens": self._settings.llm_max_tokens,
            "extra_body": self._extra_body(),
        }
        if tools:
            kwargs["tools"] = openai_tools(tools)
        attempts = 1 + self._settings.llm_max_retries
        for attempt in range(attempts):
            try:
                return self._call(kwargs)
            except _Transient as exc:
                if attempt == attempts - 1:
                    raise LLMUnavailable(f"falhou após {attempts} tentativas: {exc}") from exc
                self._wait(attempt, exc.retry_after)
        raise AssertionError("unreachable")
