"""Configuração da aplicação, lida de variáveis de ambiente (e de `.env`)."""

from datetime import date
from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # env_ignore_empty: `VAR=` no .env vale como não definida (ex.: REFERENCE_DATE, API_KEY).
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", env_ignore_empty=True
    )

    # LLM via API compatível com OpenAI (OpenRouter por padrão)
    llm_api_key: SecretStr | None = None
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "openai/gpt-oss-120b"

    database_url: str = "sqlite:///var/emporio.db"
    # Sem valor, as requisições externas não exigem autenticação.
    api_key: SecretStr | None = None
    # Data "de hoje" usada por toda regra que depende de tempo. Vazio = data real em STORE_TZ.
    reference_date: date | None = None
    store_tz: str = "America/Campo_Grande"


@lru_cache
def get_settings() -> Settings:
    return Settings()
