import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import Engine

from emporio.agent import PROMPT_VERSION, run_turn
from emporio.config import Settings
from emporio.llm import LLMUnavailable, Response, Usage
from emporio.llm.fake import FakeLLMClient, text_response, tool_call_response
from emporio.observability import TraceWriter
from tests.tools.conftest import ANA, make_ctx


def _lines(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text("utf-8").splitlines()]


def _priced(text: str, cost: float | None) -> Response:
    return Response(text=text, usage=Usage(10, 5, 2, 1, cost), model="m", provider="p")


def test_one_masked_line_per_turn(fresh_engine: Engine, tmp_path: Path) -> None:
    path = tmp_path / "t" / "turns.jsonl"
    tracer = TraceWriter(path, {"reference_date": "2026-11-27T10:00:00"})
    escalate = tool_call_response(
        "escalate_to_human",
        {
            "summary": "Ana Carolina, fone 99654-7821, anacarol.ferreira@coldmail.com",
            "category": "other",
        },
    )
    llm = FakeLLMClient([escalate, _priced("Feito, Ana!", 0.001)])
    ctx = make_ctx(fresh_engine, ANA)
    run_turn(llm, ctx, [], "sou a Ana, meu fone é (67) 99654-7821", tracer=tracer, session_id="s1")
    run_turn(FakeLLMClient([text_response("oi")]), ctx, [], "oi", tracer=tracer)

    raw = path.read_text("utf-8")
    for secret in ("Ana", "99654", "anacarol", "Carolina"):
        assert secret not in raw
    first, second = _lines(path)
    assert first["session_id"] == "s1"
    assert first["prompt_version"] == PROMPT_VERSION
    assert first["reference_date"] == "2026-11-27T10:00:00"
    assert first["stop_reason"] == "answer"
    assert first["escalated"] is True and first["protocol"].startswith("EMP-")
    assert first["tools"][0]["name"] == "escalate_to_human"
    assert first["tools"][0]["args"]["summary"] == "[nome] [nome], fone [telefone], [email]"
    assert first["user_text"] == "sou a [nome], meu fone é [telefone]"
    assert first["reply"] == "Feito, [nome]!"
    assert first["models"] == ["m"] and first["providers"] == ["p"]
    assert first["llm_calls"] == 2
    assert second["session_id"] is None


def test_cost_sum_and_tokens(fresh_engine: Engine, tmp_path: Path) -> None:
    tracer = TraceWriter(tmp_path / "t.jsonl")
    search = tool_call_response("search_products", {"query": "violão"})
    search = Response(text=None, tool_calls=search.tool_calls, usage=Usage(10, 5, 2, 1, 0.002))
    llm = FakeLLMClient([search, _priced("ok", 0.001)])
    run_turn(llm, make_ctx(fresh_engine, ANA), [], "violão", tracer=tracer)
    (line,) = _lines(tracer.path)
    assert line["cost_usd"] == 0.003
    assert line["tokens"] == {"prompt": 20, "completion": 10, "reasoning": 4, "cached": 2}


def test_cost_null_when_missing(fresh_engine: Engine, tmp_path: Path) -> None:
    tracer = TraceWriter(tmp_path / "t.jsonl")
    search = tool_call_response("search_products", {"query": "violão"})
    llm = FakeLLMClient([search, _priced("ok", 0.001)])
    run_turn(llm, make_ctx(fresh_engine, ANA), [], "violão", tracer=tracer)
    (line,) = _lines(tracer.path)
    assert line["cost_usd"] is None


def test_fallback_recorded(fresh_engine: Engine, tmp_path: Path) -> None:
    tracer = TraceWriter(tmp_path / "t.jsonl")
    run_turn(FakeLLMClient([LLMUnavailable("x")]), make_ctx(fresh_engine), [], "oi", tracer=tracer)
    (line,) = _lines(tracer.path)
    assert line["stop_reason"] == "llm_error"
    assert line["llm_error"] == "LLMUnavailable"
    assert line["tools"][0]["by"] == "code"
    assert line["customer_identified"] is False


def test_from_settings(tmp_path: Path) -> None:
    path = tmp_path / "x.jsonl"
    on = TraceWriter.from_settings(Settings(trace_path=path, reference_date=datetime(2026, 11, 26)))
    assert on is not None and on.path == path
    assert on.static == {"reference_date": "2026-11-26T00:00:00"}
    assert TraceWriter.from_settings(Settings(trace_enabled=False)) is None
