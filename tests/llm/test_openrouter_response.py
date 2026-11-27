import pytest

from emporio.llm import Message, ToolCall, Usage
from tests.llm.conftest import MakeHarness, ok, ok_body

HELLO = [Message.user("oi")]


def test_text_usage_and_provider(harness: MakeHarness) -> None:
    response = harness(ok()).client.complete(HELLO, [])
    assert response.text == "Olá!"
    assert response.tool_calls == ()
    assert response.usage == Usage(
        prompt_tokens=900,
        completion_tokens=120,
        reasoning_tokens=80,
        cached_tokens=512,
        cost_usd=pytest.approx(0.000321),
    )
    assert (response.provider, response.generation_id, response.model) == (
        "DeepInfra",
        "gen-123",
        "openai/gpt-oss-120b",
    )
    assert response.latency_ms >= 0


def test_missing_provider_and_usage(harness: MakeHarness) -> None:
    body = ok_body(provider=None)
    del body["usage"]
    response = harness(ok(body)).client.complete(HELLO, [])
    assert response.provider is None
    assert response.usage == Usage()


def test_tool_calls_keep_raw_arguments(harness: MakeHarness) -> None:
    calls = [
        {
            "id": "a",
            "type": "function",
            "function": {"name": "get_product", "arguments": '{"product_id": 95}'},
        },
        {
            "id": "b",
            "type": "function",
            "function": {"name": "get_product", "arguments": '{"product_id": '},
        },
    ]
    response = harness(
        ok(ok_body(None, tool_calls=calls, finish_reason="tool_calls"))
    ).client.complete(HELLO, [])
    assert response.text is None
    assert response.tool_calls == (
        ToolCall("a", "get_product", '{"product_id": 95}'),
        ToolCall("b", "get_product", '{"product_id": '),
    )


def test_reasoning_is_kept(harness: MakeHarness) -> None:
    response = harness(ok(ok_body(reasoning="pensando"))).client.complete(HELLO, [])
    assert response.reasoning == "pensando"
    assert response.as_message().reasoning == "pensando"
