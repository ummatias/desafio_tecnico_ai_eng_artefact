import pytest
from sqlalchemy import Engine

from emporio.config import Settings
from emporio.llm import LLMConfigError, LLMUnavailable, Message, make_llm_client
from emporio.llm.fake import FakeLLMClient, text_response, tool_call_response
from emporio.llm.openrouter import OpenRouterClient
from emporio.tools import run_tool, tool_schemas
from tests.llm.conftest import settings
from tests.tools.conftest import make_ctx


def test_fake_follows_script_and_records() -> None:
    fake = FakeLLMClient(
        [tool_call_response("get_product", {"product_id": 95}), text_response("ok")]
    )
    first = fake.complete([Message.user("gd20?")], tool_schemas())
    second = fake.complete([Message.user("gd20?"), first.as_message()], tool_schemas())
    assert first.tool_calls[0].arguments == '{"product_id": 95}'
    assert second.text == "ok"
    assert [len(r.messages) for r in fake.requests] == [1, 2]
    assert len(fake.requests[0].tools) == 7


def test_fake_exhausted_script() -> None:
    fake = FakeLLMClient([])
    with pytest.raises(AssertionError, match="roteiro esgotado"):
        fake.complete([Message.user("oi")], [])


def test_fake_can_raise_llm_errors() -> None:
    fake = FakeLLMClient([LLMUnavailable("fora do ar")])
    with pytest.raises(LLMUnavailable):
        fake.complete([Message.user("oi")], [])


def test_malformed_tool_arguments_become_tool_error(seeded_engine: Engine) -> None:
    """Argumento malformado do modelo volta como erro de tool, nunca como exceção."""
    call = tool_call_response("get_product", '{"product_id": ').tool_calls[0]
    result = run_tool(call.name, call.arguments, make_ctx(seeded_engine))
    assert result["error"] == "invalid_arguments"


def test_factory_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    with pytest.raises(LLMConfigError, match="LLM_API_KEY"):
        make_llm_client(Settings(_env_file=None))


def test_factory_builds_openrouter_client() -> None:
    assert isinstance(make_llm_client(settings()), OpenRouterClient)


def test_provider_order_parsing() -> None:
    assert settings(llm_providers=" deepinfra, ,groq ").llm_provider_order == ["deepinfra", "groq"]
    assert settings().llm_provider_order == []
