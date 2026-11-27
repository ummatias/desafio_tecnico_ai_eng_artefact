import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import func, select
from typer.testing import CliRunner

from emporio import cli
from emporio.config import Settings, get_settings
from emporio.db.engine import make_engine
from emporio.db.schema import customers
from emporio.llm import LLMClient, Message, Response
from emporio.llm.fake import FakeLLMClient, text_response, tool_call_response
from tests.conftest import DATA_DIR, KNOWLEDGE_DIR, ROOT

ANA = "(67) 99654-7821"


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'e.db'}")
    monkeypatch.setenv("TRACE_PATH", str(tmp_path / "t.jsonl"))
    monkeypatch.setenv("TRACE_ENABLED", "true")
    monkeypatch.setenv("REFERENCE_DATE", "2026-11-26")
    monkeypatch.setenv("DATA_DIR", str(DATA_DIR))
    monkeypatch.setenv("KNOWLEDGE_DIR", str(KNOWLEDGE_DIR))
    monkeypatch.setenv("ASSUMPTIONS_PATH", str(ROOT / "docs" / "assumptions.md"))
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.chdir(tmp_path)
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


def _fake(monkeypatch: pytest.MonkeyPatch, script: list[Response]) -> FakeLLMClient:
    llm = FakeLLMClient(script)

    def factory(_settings: Settings) -> LLMClient:
        return llm

    monkeypatch.setattr(cli, "make_llm_client", factory)
    return llm


def _chat(stdin: str, *args: str) -> tuple[int, str]:
    result = CliRunner().invoke(cli.app, ["chat", *args], input=stdin)
    return result.exit_code, result.output


def test_seeds_empty_db_and_shows_banner(env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fake(monkeypatch, [])
    code, out = _chat("/sair\n", "--phone", ANA)
    assert code == 0
    engine = make_engine(f"sqlite:///{env / 'e.db'}")
    with engine.connect() as conn:
        assert conn.execute(select(func.count()).select_from(customers)).scalar_one() > 0
    engine.dispose()
    assert "Ana (Campo Grande)" in out
    assert "26/11/2026 10:00" in out
    assert "TRACKING_SOURCE: none" in out


def test_turn_prints_reply_and_writes_trace(env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fake(monkeypatch, [text_response("Oi! Como posso ajudar?")])
    code, out = _chat("oi\n/sair\n", "--phone", ANA, "--session-id", "s1")
    assert code == 0
    assert "Empório: Oi! Como posso ajudar?" in out
    lines = (env / "t.jsonl").read_text("utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["session_id"] == "s1"


def test_history_and_clear(env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    llm = _fake(monkeypatch, [text_response("um"), text_response("dois"), text_response("três")])
    code, _ = _chat("oi\ne aí?\n/limpar\nde novo\n/sair\n", "--phone", ANA)
    assert code == 0
    second, third = llm.requests[1].messages, llm.requests[2].messages
    assert second[1:3] == (Message.user("oi"), Message("assistant", "um"))
    assert second[3] == Message.user("e aí?")
    assert [m.role for m in third] == ["system", "user"]


def test_unknown_phone_warns_and_continues(env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fake(monkeypatch, [text_response("Oi!")])
    code, out = _chat("oi\n/sair\n", "--phone", "(67) 90000-0000")
    assert code == 0
    assert "Telefone não cadastrado" in out
    assert "Cliente: não identificado" in out
    assert "Empório: Oi!" in out


def test_missing_key_exits_2(env: Path) -> None:
    code, out = _chat("oi\n")
    assert code == cli.EXIT_CONFIG
    assert "LLM_API_KEY" in out


def test_debug_shows_tools_and_stop_reason(env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    search = tool_call_response("search_products", {"query": "takamine gd 20"})
    _fake(monkeypatch, [search, text_response("Tenho o GD20!")])
    code, out = _chat("tem gd20?\n/sair\n", "--phone", ANA, "--debug")
    assert code == 0
    assert "search_products" in out
    assert "stop_reason=answer" in out


def test_reply_printed_literally(env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fake(monkeypatch, [text_response("Oi, [nome]! [bold]x[/bold]")])
    _, out = _chat("oi\n/sair\n")
    assert "Empório: Oi, [nome]! [bold]x[/bold]" in out


def test_blank_line_and_eof(env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    llm = _fake(monkeypatch, [])
    code, _ = _chat("\n   \n")
    assert code == 0
    assert llm.requests == []
