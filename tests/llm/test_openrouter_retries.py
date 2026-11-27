"""Retries (D-45) com o `sleep` injetado: nenhum teste espera de verdade."""

import httpx2
import pytest

from emporio.llm import LLMRejected, LLMTruncated, LLMUnavailable, Message
from tests.llm.conftest import MakeHarness, error_body, ok, ok_body

HELLO = [Message.user("oi")]


def test_429_respects_retry_after(harness: MakeHarness) -> None:
    h = harness((429, error_body(429, "rate limited"), {"Retry-After": "2"}), ok())
    assert h.client.complete(HELLO, []).text == "Olá!"
    assert h.sleeps == [2.0]
    assert len(h.server.requests) == 2


def test_503_until_exhausted(harness: MakeHarness) -> None:
    replies = [(503, error_body(503, "overloaded", "provider_overloaded"), {})] * 3
    h = harness(*replies)
    with pytest.raises(LLMUnavailable, match="3 tentativas"):
        h.client.complete(HELLO, [])
    assert len(h.server.requests) == 3  # 1 + LLM_MAX_RETRIES (2)
    assert h.sleeps == [1.0, 2.0]  # backoff exponencial (jitter fixo em 1.0)


def test_error_inside_http_200_is_retried(harness: MakeHarness) -> None:
    h = harness((200, error_body(503, "busy", "provider_overloaded"), {}), ok())
    assert h.client.complete(HELLO, []).text == "Olá!"
    assert len(h.server.requests) == 2


def test_finish_reason_error_is_retried(harness: MakeHarness) -> None:
    body = ok_body("parcial", finish_reason="error")
    body["choices"][0]["error"] = {
        "code": 502,
        "message": "x",
        "metadata": {"error_type": "server"},
    }
    h = harness((200, body, {}), ok())
    assert h.client.complete(HELLO, []).text == "Olá!"


def test_non_transient_error_inside_200(harness: MakeHarness) -> None:
    h = harness((200, error_body(400, "context too long", "invalid_request"), {}))
    with pytest.raises(LLMUnavailable, match="context too long"):
        h.client.complete(HELLO, [])
    assert len(h.server.requests) == 1


@pytest.mark.parametrize("status", [400, 401, 402, 403])
def test_4xx_is_not_retried(harness: MakeHarness, status: int) -> None:
    h = harness((status, error_body(status, "nope"), {}))
    with pytest.raises(LLMRejected) as info:
        h.client.complete(HELLO, [])
    assert info.value.status == status
    assert len(h.server.requests) == 1
    assert h.sleeps == []


def test_404_no_provider_mentions_data_collection(harness: MakeHarness) -> None:
    h = harness((404, error_body(404, "No endpoints found matching your data policy"), {}))
    with pytest.raises(LLMRejected, match="LLM_DATA_COLLECTION") as info:
        h.client.complete(HELLO, [])
    assert info.value.status == 404
    assert "LLM_PROVIDERS" in str(info.value)
    assert len(h.server.requests) == 1


def test_402_with_retry_after_is_retried(harness: MakeHarness) -> None:
    h = harness((402, error_body(402, "in-flight budget"), {"Retry-After": "1"}), ok())
    assert h.client.complete(HELLO, []).text == "Olá!"


def test_timeout_is_retried_then_unavailable(harness: MakeHarness) -> None:
    timeout = httpx2.ReadTimeout("timed out")
    h = harness(timeout, timeout, timeout)
    with pytest.raises(LLMUnavailable):
        h.client.complete(HELLO, [])
    assert len(h.server.requests) == 3


def test_timeout_then_success(harness: MakeHarness) -> None:
    h = harness(httpx2.ConnectError("refused"), ok())
    assert h.client.complete(HELLO, []).text == "Olá!"


def test_empty_length_response_is_truncated_without_retry(harness: MakeHarness) -> None:
    h = harness(ok(ok_body(None, finish_reason="length")))
    with pytest.raises(LLMTruncated, match="LLM_MAX_TOKENS"):
        h.client.complete(HELLO, [])
    assert len(h.server.requests) == 1


def test_length_with_text_is_returned(harness: MakeHarness) -> None:
    response = harness(ok(ok_body("meio", finish_reason="length"))).client.complete(HELLO, [])
    assert (response.text, response.finish_reason) == ("meio", "length")
