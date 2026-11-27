import json

from emporio.llm import Message, ToolCall
from emporio.llm.schemas import inline_refs, openai_tools
from emporio.tools import tool_schemas
from tests.llm.conftest import MakeHarness, ok, ok_body

HELLO = [Message.system("Você é o assistente."), Message.user("oi")]


def test_body_has_model_messages_and_tools(harness: MakeHarness) -> None:
    h = harness(ok())
    h.client.complete(HELLO, tool_schemas())
    [body] = h.server.bodies()
    assert body["model"] == "openai/gpt-oss-120b"
    assert body["messages"] == [
        {"role": "system", "content": "Você é o assistente."},
        {"role": "user", "content": "oi"},
    ]
    assert body["max_tokens"] == 2048
    names = [t["function"]["name"] for t in body["tools"]]
    assert names[0] == "search_products" and len(names) == 7
    assert all(t["type"] == "function" for t in body["tools"])
    assert "$ref" not in json.dumps(body["tools"])
    assert "$defs" not in json.dumps(body["tools"])


def test_quote_cart_items_inlined() -> None:
    [quote] = [t for t in openai_tools(tool_schemas()) if t["function"]["name"] == "quote_cart"]
    item = quote["function"]["parameters"]["properties"]["items"]["items"]
    assert set(item["properties"]) == {"product_id", "quantity"}


def test_inline_refs_rejects_cycles() -> None:
    schema = {"$defs": {"A": {"$ref": "#/$defs/A"}}, "properties": {"a": {"$ref": "#/$defs/A"}}}
    try:
        inline_refs(schema)
    except ValueError as exc:
        assert "$ref" in str(exc)
    else:
        raise AssertionError("ciclo não detectado")


def test_provider_routing_defaults(harness: MakeHarness) -> None:
    h = harness(ok())
    h.client.complete(HELLO, [])
    [body] = h.server.bodies()
    assert body["provider"] == {"data_collection": "deny", "require_parameters": True}
    assert "reasoning" not in body
    assert "tools" not in body


def test_pinned_providers_without_fallbacks(harness: MakeHarness) -> None:
    h = harness(ok(), llm_providers="deepinfra, groq", llm_reasoning_effort="low")
    h.client.complete(HELLO, [])
    [body] = h.server.bodies()
    assert body["provider"]["order"] == ["deepinfra", "groq"]
    assert body["provider"]["allow_fallbacks"] is False
    assert body["reasoning"] == {"effort": "low"}


def test_no_attribution_headers(harness: MakeHarness) -> None:
    h = harness(ok())
    h.client.complete(HELLO, [])
    headers = {k.lower() for k in h.server.requests[0].headers}
    assert "http-referer" not in headers
    assert "x-title" not in headers
    assert h.server.requests[0].headers["authorization"] == "Bearer sk-or-test"


def test_reasoning_and_tool_calls_sent_back(harness: MakeHarness) -> None:
    """D-46: a mensagem do assistente volta com tool_calls e reasoning_details."""
    details = [{"type": "reasoning.text", "text": "preciso do preço"}]
    call = {"id": "c1", "type": "function", "function": {"name": "get_product", "arguments": "{}"}}
    h = harness(ok(ok_body(None, tool_calls=[call], reasoning_details=details)), ok())
    first = h.client.complete(HELLO, tool_schemas())
    history = [*HELLO, first.as_message(), Message.tool("c1", '{"price": "R$ 2.199,00"}')]
    h.client.complete(history, tool_schemas())
    sent = h.server.bodies()[1]["messages"]
    assert sent[2] == {
        "role": "assistant",
        "content": None,
        "tool_calls": [call],
        "reasoning_details": details,
    }
    assert sent[3] == {"role": "tool", "content": '{"price": "R$ 2.199,00"}', "tool_call_id": "c1"}


def test_reasoning_text_sent_back_without_details(harness: MakeHarness) -> None:
    h = harness(ok())
    message = Message("assistant", "ok", tool_calls=(ToolCall("c", "x", "{}"),), reasoning="r")
    h.client.complete([*HELLO, message], [])
    assert h.server.bodies()[0]["messages"][2]["reasoning"] == "r"
