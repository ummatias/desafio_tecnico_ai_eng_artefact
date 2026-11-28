from pathlib import Path

import pytest
from sqlalchemy import Engine

import emporio.evals.runner as runner_module
from emporio.config import Settings
from emporio.evals.runner import case_settings, run_case, run_suite
from emporio.llm import LLMClient, Message, Response
from emporio.llm.fake import FakeLLMClient, text_response, tool_call_response
from emporio.observability import TraceWriter
from tests.conftest import DATA_DIR, KNOWLEDGE_DIR, ROOT
from tests.evals.conftest import make_case

RAFAEL = "(67) 98765-4321"


def _settings() -> Settings:
    return Settings(
        data_dir=DATA_DIR,
        knowledge_dir=KNOWLEDGE_DIR,
        assumptions_path=ROOT / "docs" / "assumptions.md",
        delivery_events_path=ROOT / "fixtures" / "delivery_events.csv",
        trace_enabled=False,
    )


def test_case_settings_overrides_date_and_tracking() -> None:
    case = make_case(reference_date="2026-01-20T10:00", session={"tracking_source": "fixture"})
    settings = case_settings(_settings(), case)
    assert settings.reference_date is not None and settings.reference_date.day == 20
    assert settings.tracking_source == "fixture"


def test_two_turns_share_history() -> None:
    case = make_case(turns=[{"user": "oi"}, {"user": "e aí?", "expected_facts": ["dois"]}])
    llm = FakeLLMClient([text_response("um"), text_response("dois")])
    record = run_case(case, _settings(), llm)
    assert record.passed
    second = llm.requests[1].messages
    assert second[1:3] == (Message.user("oi"), Message("assistant", "um"))


def test_fixture_and_reference_date_drive_the_engine() -> None:
    """Pedido 5 entregue em 12/01/2026 (fixture); em 20/01 o arrependimento expirou."""
    case = make_case(
        category="exchange",
        reference_date="2026-01-20T10:00",
        session={"phone": RAFAEL, "tracking_source": "fixture"},
        turns=[{"user": "quero devolver o pedido 5"}],
        expected_outcome={"outcome": "expired", "sections": ["4.1"]},
    )
    call = tool_call_response(
        "check_exchange", {"order_id": 5, "product_id": 97, "reason": "regret"}
    )
    record = run_case(case, _settings(), FakeLLMClient([call, text_response("Expirou.")]))
    outcome = next(c for c in record.checks if c.name == "outcome")
    assert outcome.status == "pass", outcome.detail


def test_each_run_has_a_fresh_database(monkeypatch: pytest.MonkeyPatch) -> None:
    case = make_case(category="escalation", session={"phone": RAFAEL}, should_escalate=True)
    escalate = tool_call_response(
        "escalate_to_human", {"summary": "Reclamação", "category": "complaint"}
    )
    engines: list[Engine] = []
    original = runner_module.make_engine

    def spy(url: str) -> Engine:
        engine = original(url)
        engines.append(engine)
        return engine

    monkeypatch.setattr(runner_module, "make_engine", spy)
    llm = FakeLLMClient([escalate, text_response("ok"), escalate, text_response("ok")])
    suite = run_suite([case], _settings(), llm, runs=2)
    assert [r.passed for r in suite.records] == [True, True]
    assert len(engines) == 2 and engines[0] is not engines[1]
    protocols = [r.turns[0].protocol for r in suite.records]
    assert protocols[0] == protocols[1]  # mesmo número: cada banco começa vazio


def test_broken_run_is_recorded_not_raised() -> None:
    class Boom:
        def complete(self, messages: object, tools: object) -> Response:
            raise RuntimeError("quebrou")

    llm: LLMClient = Boom()  # type: ignore[assignment]
    record = run_case(make_case(), _settings(), llm)
    assert not record.passed and record.error is not None and "quebrou" in record.error


def test_trace_lines_are_tagged_with_case_and_run(tmp_path: Path) -> None:
    tracer = TraceWriter(tmp_path / "t.jsonl")
    run_suite(
        [make_case()], _settings(), FakeLLMClient([text_response("a")] * 2), runs=2, tracer=tracer
    )
    text = (tmp_path / "t.jsonl").read_text("utf-8")
    assert '"session_id": "caso#1"' in text and '"session_id": "caso#2"' in text


def test_configured_database_is_never_used(tmp_path: Path) -> None:
    """Cada execução usa um banco em memória, nunca o DATABASE_URL."""
    db = tmp_path / "nao-usar.db"
    settings = _settings().model_copy(update={"database_url": f"sqlite:///{db}"})
    record = run_case(make_case(), settings, FakeLLMClient([text_response("ok")]))
    assert record.passed
    assert not db.exists()
