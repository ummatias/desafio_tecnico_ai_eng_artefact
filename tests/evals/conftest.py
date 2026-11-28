from collections.abc import Sequence
from typing import Any

from emporio.agent import ToolRun, TurnResult
from emporio.evals.cases import EvalCase
from emporio.llm import Message, Response, Usage


def make_turn(
    reply: str,
    *,
    tools: Sequence[tuple[str, dict[str, Any]]] = (),
    escalated: bool = False,
    cost: float | None = 0.001,
    latency_ms: float = 1000.0,
    provider: str | None = "p",
) -> TurnResult:
    runs = tuple(ToolRun(name, "{}", result, 1.0) for name, result in tools)
    response = Response(text=reply, usage=Usage(10, 5, 1, 0, cost), provider=provider)
    return TurnResult(
        reply=reply,
        stop_reason="answer",
        iterations=1,
        tool_runs=runs,
        responses=(response,),
        escalated=escalated,
        protocol="EMP-20261126-0001" if escalated else None,
        llm_error=None,
        latency_ms=latency_ms,
        transcript=(Message.user("u"), Message("assistant", reply)),
    )


def make_case(**overrides: Any) -> EvalCase:
    data: dict[str, Any] = {
        "id": "caso",
        "category": "product",
        "source": "§3",
        "reference_date": "2026-11-26T10:00",
        "turns": [{"user": "oi"}],
    }
    data.update(overrides)
    return EvalCase.model_validate(data)
