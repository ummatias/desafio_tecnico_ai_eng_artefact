from typing import Any

import pytest

from emporio.evals.checks import Check
from emporio.evals.judge import Verdict
from emporio.evals.report import case_status, compare, render_markdown, summarize
from emporio.evals.runner import RunRecord, SuiteResult
from emporio.evals.stats import percentile, wilson
from tests.evals.conftest import make_case, make_turn


def test_wilson_matches_plan_numbers() -> None:
    low, high = wilson(20, 25)
    assert round(low, 2) == 0.61 and round(high, 2) == 0.91
    low, high = wilson(12, 15)
    assert round(low, 2) == 0.55 and round(high, 2) == 0.93
    assert wilson(0, 5)[0] == 0.0 and wilson(5, 5)[1] == 1.0


def test_wilson_rejects_bad_input() -> None:
    with pytest.raises(ValueError):
        wilson(1, 0)
    with pytest.raises(ValueError):
        wilson(3, 2)


def test_percentile() -> None:
    assert percentile([], 50) is None
    assert percentile([3.0, 1.0, 2.0, 4.0], 50) == 2.0
    assert percentile([3.0, 1.0, 2.0, 4.0], 95) == 4.0


@pytest.mark.parametrize(
    ("passes", "status"),
    [([True] * 3, "stable_pass"), ([False] * 3, "stable_fail"), ([True, False, True], "flaky")],
)
def test_case_status(passes: list[bool], status: str) -> None:
    assert case_status(passes) == status


def _record(case_id: str, i: int, passed: bool, *, escalated: bool = False, **kw: Any) -> RunRecord:
    checks = (Check("facts", "pass" if passed else "fail", "" if passed else "turn 1: x"),)
    return RunRecord(case_id, i, (make_turn("r", escalated=escalated),), checks, passed, **kw)


def _suite() -> SuiteResult:
    a = make_case(id="a")
    b = make_case(id="b", should_refuse=True)
    records = (
        *(_record("a", i, True, escalated=i < 3) for i in (1, 2, 3)),
        _record("b", 1, True, verdict=Verdict(5, True, "ok")),
        _record("b", 2, False, verdict=Verdict(3, False, "frio")),
        _record("b", 3, True, verdict=Verdict(4, True, "ok")),
    )
    return SuiteResult(model="m", runs_per_case=3, cases=(a, b), records=records)


def test_summarize_counts_cases_not_runs() -> None:
    summary = summarize(_suite())
    assert summary["status_counts"] == {"stable_pass": 1, "flaky": 1, "stable_fail": 0}
    assert summary["pass_rate"]["k"] == 1 and summary["pass_rate"]["n"] == 2
    assert summary["metrics"]["facts"]["n"] == 2
    # Recusa só se aplica a b (should_refuse); falhou numa das 3 execuções.
    assert summary["metrics"]["refusal"] == {**summary["metrics"]["refusal"], "k": 0, "n": 1}
    assert summary["metrics"]["tone"]["n"] == 1
    # a escalou em 2 de 3 execuções: conta como escalado.
    assert summary["escalation_rate"]["k"] == 1
    assert summary["cost_usd"]["total"] == pytest.approx(0.006)
    assert summary["providers"] == ["p"]


def test_markdown_has_row_per_case() -> None:
    text = render_markdown(summarize(_suite()))
    assert "| a | product | stable_pass | 3/3 | - |" in text
    assert "| b | product | flaky | 2/3 | facts: turn 1: x |" in text
    assert "meta ≤ 25%" in text
    assert "guard" in text


def test_cost_unknown_when_any_missing() -> None:
    case = make_case(id="a")
    record = RunRecord("a", 1, (make_turn("r", cost=None),), (), True)
    summary = summarize(SuiteResult("m", 1, (case,), (record,)))
    assert summary["cost_usd"]["total"] is None


def test_compare_buckets() -> None:
    def results(statuses: dict[str, str]) -> dict[str, Any]:
        return {"cases": [{"id": k, "status": v} for k, v in statuses.items()]}

    a = results({"x": "stable_pass", "y": "stable_pass", "z": "flaky", "w": "stable_fail"})
    b = results({"x": "stable_pass", "y": "flaky", "z": "stable_pass", "w": "stable_fail"})
    assert compare(a, b) == {"only_a": ["y"], "only_b": ["z"], "both": ["x"], "neither": ["w"]}
