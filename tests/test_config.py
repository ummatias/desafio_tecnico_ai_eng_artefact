from datetime import datetime

import pytest

from emporio.config import Settings

ENV_VARS = (
    "LLM_API_KEY",
    "LLM_BASE_URL",
    "LLM_MODEL",
    "DATABASE_URL",
    "API_KEY",
    "REFERENCE_DATE",
    "STORE_TZ",
    "TRACKING_SOURCE",
    "STALLED_AFTER_BUSINESS_DAYS",
    "LLM_TIMEOUT_SECONDS",
    "LLM_MAX_RETRIES",
    "LLM_MAX_TOKENS",
    "LLM_PROVIDERS",
    "LLM_DATA_COLLECTION",
    "LLM_REASONING_EFFORT",
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ENV_VARS:
        monkeypatch.delenv(var, raising=False)


def test_defaults_without_env() -> None:
    settings = Settings(_env_file=None)

    assert settings.llm_api_key is None
    assert settings.llm_base_url == "https://openrouter.ai/api/v1"
    assert settings.llm_model == "openai/gpt-oss-120b"
    assert settings.api_key is None
    assert settings.reference_date is None
    assert settings.store_tz == "America/Campo_Grande"
    assert settings.llm_data_collection == "deny"
    assert settings.llm_provider_order == []
    assert settings.llm_reasoning_effort is None


def test_reference_date_only_means_10am(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REFERENCE_DATE", "2025-11-28")

    assert Settings(_env_file=None).reference_date == datetime(2025, 11, 28, 10, 0)


def test_reference_date_with_time(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REFERENCE_DATE", "2026-11-26T17:30")

    assert Settings(_env_file=None).reference_date == datetime(2026, 11, 26, 17, 30)


def test_empty_values_count_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REFERENCE_DATE", "")
    monkeypatch.setenv("API_KEY", "")

    settings = Settings(_env_file=None)

    assert settings.reference_date is None
    assert settings.api_key is None


def test_secrets_are_not_printed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_API_KEY", "sk-or-v1-secret")

    settings = Settings(_env_file=None)

    assert "sk-or-v1-secret" not in repr(settings)
    assert settings.llm_api_key is not None
    assert settings.llm_api_key.get_secret_value() == "sk-or-v1-secret"


def test_env_example_loads() -> None:
    settings = Settings(_env_file=".env.example")

    assert settings.llm_base_url == "https://openrouter.ai/api/v1"
    assert settings.reference_date is None
    assert settings.api_key is None
