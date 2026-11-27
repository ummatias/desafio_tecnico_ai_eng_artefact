"""Configuração da aplicação, lida de variáveis de ambiente (e de `.env`)."""

from datetime import date, datetime, time
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_REFERENCE_TIME = time(10)


class Settings(BaseSettings):
    # env_ignore_empty: `VAR=` no .env vale como não definida (ex.: REFERENCE_DATE, API_KEY).
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", env_ignore_empty=True
    )

    # LLM via API compatível com OpenAI (OpenRouter por padrão)
    llm_api_key: SecretStr | None = None
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "openai/gpt-oss-120b"
    llm_timeout_seconds: float = Field(default=30, gt=0)
    llm_max_retries: int = Field(default=2, ge=0, le=5)
    llm_max_tokens: int = Field(default=2048, ge=256)
    # Providers do OpenRouter em ordem, separados por vírgula; vazio = roteamento padrão.
    # Com valor, não há fallback para outros providers (evals e comparação, commit 13).
    llm_providers: str = ""
    # "deny": só providers que não guardam os dados (as mensagens têm dados de clientes
    llm_data_collection: Literal["allow", "deny"] = "deny"
    llm_reasoning_effort: Literal["low", "medium", "high"] | None = None

    database_url: str = "sqlite:///var/emporio.db"
    # CSVs originais (somente leitura) e base de conhecimento curada
    data_dir: Path = Path("data")
    knowledge_dir: Path = Path("knowledge")
    # Texto das premissas, devolvido pela get_policy junto com cada seção
    assumptions_path: Path = Path("docs/assumptions.md")
    # Sem valor, as requisições externas não exigem autenticação.
    api_key: SecretStr | None = None
    # "Agora" usado por toda regra que depende de tempo (REFERENCE_DATE), no fuso STORE_TZ.
    # Aceita data com hora (2026-11-26T10:00); só a data vale às 10:00. Vazio = relógio real.
    reference_date: datetime | None = None
    store_tz: str = "America/Campo_Grande"
    # Fonte da data de recebimento: "none" (padrão: prazos do recebimento dão to_confirm)
    # ou "fixture" (eventos SINTÉTICOS, só em exemplos e evals).
    tracking_source: Literal["none", "fixture"] = "none"
    delivery_events_path: Path = Path("fixtures/delivery_events.csv")
    # P-08: pedido pending/confirmed há mais que isso (dias úteis) fica "stalled".
    stalled_after_business_days: int = Field(default=5, ge=1)
    # Trace JSONL, uma linha por turno, com dados pessoais mascarados.
    trace_enabled: bool = True
    trace_path: Path = Path("var/traces/turns.jsonl")

    @property
    def llm_provider_order(self) -> list[str]:
        return [p.strip() for p in self.llm_providers.split(",") if p.strip()]

    @field_validator("reference_date", mode="before")
    @classmethod
    def _date_only_at_ten(cls, value: object) -> object:
        if isinstance(value, str) and len(value.strip()) == 10:
            return datetime.combine(date.fromisoformat(value.strip()), DEFAULT_REFERENCE_TIME)
        if isinstance(value, date) and not isinstance(value, datetime):
            return datetime.combine(value, DEFAULT_REFERENCE_TIME)
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
