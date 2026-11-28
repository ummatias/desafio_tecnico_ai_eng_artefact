import pytest

from emporio.evals.checks import check_run, normalize, run_passed
from tests.evals.conftest import make_case, make_turn


def _status(case_kw: dict[str, object], *turns: object) -> dict[str, str]:
    case = make_case(**case_kw)
    return {c.name: c.status for c in check_run(case, turns)}  # type: ignore[arg-type]


NBSP, NARROW_NBSP, NB_HYPHEN = chr(0x00A0), chr(0x202F), chr(0x2011)


def test_normalize() -> None:
    assert normalize(f"**R${NBSP}2.199,00**") == "r$ 2.199,00"
    assert normalize(f"sexta{NB_HYPHEN}feira  às\n18:00") == "sexta-feira às 18:00"
    assert normalize(f"R${NARROW_NBSP}35,00") == "r$ 35,00"
    assert (
        normalize(f"8{NARROW_NBSP}% de desconto") == normalize("8% de desconto") == "8% de desconto"
    )


def test_facts_any_of_and_missing() -> None:
    turns = [
        {"user": "oi", "expected_facts": ["R$ 2.199,00", {"any_of": ["esgotado", "sem estoque"]}]}
    ]
    ok = make_turn("Custa **R$ 2.199,00**, mas está sem estoque.")
    bad = make_turn("Custa R$ 2.199,00.")
    assert _status({"turns": turns}, ok)["facts"] == "pass"
    checks = check_run(make_case(turns=turns), [bad])
    facts = next(c for c in checks if c.name == "facts")
    assert facts.status == "fail" and "esgotado | sem estoque" in facts.detail


def test_facts_are_checked_per_turn() -> None:
    turns = [{"user": "a", "expected_facts": ["18:00"]}, {"user": "b"}]
    status = _status({"turns": turns}, make_turn("sem horário"), make_turn("18:00"))
    assert status["facts"] == "fail"


def test_must_not_case_level_applies_to_every_turn() -> None:
    kw = {"turns": [{"user": "a"}, {"user": "b"}], "must_not_include": ["GF-3D"]}
    assert _status(kw, make_turn("ok"), make_turn("o gf-3d"))["must_not"] == "fail"
    assert _status(kw, make_turn("ok"), make_turn("ok"))["must_not"] == "pass"


def test_tools_subset_and_forbidden() -> None:
    kw = {"expected_tools": ["search_products"], "forbidden_tools": ["get_order"]}
    assert _status(kw, make_turn("x", tools=[("search_products", {})]))["tools"] == "pass"
    assert _status(kw, make_turn("x"))["tools"] == "fail"
    both = make_turn("x", tools=[("search_products", {}), ("get_order", {})])
    assert _status(kw, both)["tools"] == "fail"


def test_outcome_and_sections() -> None:
    kw = {"expected_outcome": {"outcome": "to_confirm", "sections": ["4.1"]}}
    good = make_turn(
        "x", tools=[("check_exchange", {"outcome": "to_confirm", "sections": ["4.1", "4.4"]})]
    )
    wrong = make_turn("x", tools=[("check_exchange", {"outcome": "expired", "sections": ["4.1"]})])
    error = make_turn("x", tools=[("check_exchange", {"error": "not_found"})])
    assert _status(kw, good)["outcome"] == "pass"
    assert _status(kw, wrong)["outcome"] == "fail"
    assert _status(kw, error)["outcome"] == "fail"


@pytest.mark.parametrize(
    ("should", "escalated", "expected"),
    [(True, True, "pass"), (True, False, "fail"), (False, True, "fail"), (None, True, "na")],
)
def test_escalation(should: bool | None, escalated: bool, expected: str) -> None:
    status = _status({"should_escalate": should}, make_turn("x", escalated=escalated))
    assert status["escalation"] == expected


def test_run_passed_ignores_na() -> None:
    case = make_case()
    checks = check_run(case, [make_turn("x")])
    assert all(c.status == "na" for c in checks)
    assert run_passed(checks)


def test_turn_count_must_match() -> None:
    with pytest.raises(ValueError, match="one TurnResult"):
        check_run(make_case(), [])
