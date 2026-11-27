"""Chamada real ao OpenRouter. Fora do `pytest` padrão; rode com `uv run pytest -m live`."""

import pytest

from emporio.config import Settings
from emporio.llm import Message, make_llm_client
from emporio.tools import tool_schemas

pytestmark = pytest.mark.live


def test_live_tool_call() -> None:
    settings = Settings()
    if settings.llm_api_key is None:
        pytest.skip("LLM_API_KEY não definida")
    client = make_llm_client(settings)
    response = client.complete(
        [
            Message.system("Use as tools para responder. Não invente preços."),
            Message.user("Quanto custa o produto 95?"),
        ],
        tool_schemas(),
    )
    print(
        f"provider={response.provider} cost={response.usage.cost_usd} {response.latency_ms:.0f}ms"
    )
    assert [c.name for c in response.tool_calls] == ["get_product"]
    assert response.usage.cost_usd is not None and response.usage.cost_usd > 0
