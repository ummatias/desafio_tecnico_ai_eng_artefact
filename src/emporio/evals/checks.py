"""Pontuação de uma execução de caso: só código, sem LLM."""

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from emporio.agent import TurnResult
from emporio.evals.cases import AnyOf, EvalCase, Fact

Status = Literal["pass", "fail", "na"]
CHECKS = ("tools", "facts", "must_not", "outcome", "escalation")

# Hífens e traços que o modelo usa (ex.: U+2011 em "sexta-feira") viram "-".
_DASHES = dict.fromkeys((0x2010, 0x2011, 0x2012, 0x2013, 0x2014, 0x2212), "-")
_NBSP = {0x00A0: " ", 0x202F: " "}
_SPACES = re.compile(r"\s+")
_MARKDOWN = re.compile(r"[*_`]")


@dataclass(frozen=True)
class Check:
    name: str
    status: Status
    detail: str = ""


_PERCENT = re.compile(r"(\d)\s+%")


def normalize(text: str) -> str:
    """Compara texto como o cliente lê: sem markdown, hífens e espaços especiais unificados."""
    text = unicodedata.normalize("NFKC", text).translate(_DASHES)
    text = text.translate(_NBSP)
    text = _MARKDOWN.sub("", text)
    text = _PERCENT.sub(r"\1%", text)  # "8 %" e "8%" são a mesma coisa
    return _SPACES.sub(" ", text).strip().casefold()


def _matches(fact: Fact, reply: str) -> bool:
    options = fact.any_of if isinstance(fact, AnyOf) else (fact,)
    return any(normalize(option) in reply for option in options)


def _label(fact: Fact) -> str:
    return " | ".join(fact.any_of) if isinstance(fact, AnyOf) else fact


def _tools(case: EvalCase, turns: Sequence[TurnResult]) -> Check:
    if not case.expected_tools and not case.forbidden_tools:
        return Check("tools", "na")
    called = {r.name for t in turns for r in t.tool_runs if r.by == "model"}
    missing = [t for t in case.expected_tools if t not in called]
    forbidden = [t for t in case.forbidden_tools if t in called]
    problems = [f"missing {missing}"] * bool(missing) + [f"forbidden {forbidden}"] * bool(forbidden)
    return Check("tools", "fail" if problems else "pass", "; ".join(problems))


def _facts(case: EvalCase, turns: Sequence[TurnResult]) -> Check:
    if not any(t.expected_facts for t in case.turns):
        return Check("facts", "na")
    missing = [
        f"turn {i + 1}: {_label(fact)}"
        for i, (turn, result) in enumerate(zip(case.turns, turns, strict=True))
        for fact in turn.expected_facts
        if not _matches(fact, normalize(result.reply))
    ]
    return Check("facts", "fail" if missing else "pass", "; ".join(missing))


def _must_not(case: EvalCase, turns: Sequence[TurnResult]) -> Check:
    pairs = [
        (i, text)
        for i, turn in enumerate(case.turns)
        for text in (*turn.must_not_include, *case.must_not_include)
    ]
    if not pairs:
        return Check("must_not", "na")
    found = [
        f"turn {i + 1}: {text}" for i, text in pairs if normalize(text) in normalize(turns[i].reply)
    ]
    return Check("must_not", "fail" if found else "pass", "; ".join(found))


def _outcome(case: EvalCase, turns: Sequence[TurnResult]) -> Check:
    expected = case.expected_outcome
    if expected is None:
        return Check("outcome", "na")
    results = [
        r.result
        for t in turns
        for r in t.tool_runs
        if r.name == expected.tool and "outcome" in r.result
    ]
    if not results:
        return Check("outcome", "fail", f"{expected.tool} not called successfully")
    last = results[-1]
    sections = set(last.get("sections", []))
    problems = []
    if last["outcome"] != expected.outcome:
        problems.append(f"outcome {last['outcome']} != {expected.outcome}")
    if not set(expected.sections) <= sections:
        problems.append(f"sections {sorted(sections)} lack {list(expected.sections)}")
    return Check("outcome", "fail" if problems else "pass", "; ".join(problems))


def _escalation(case: EvalCase, turns: Sequence[TurnResult]) -> Check:
    if case.should_escalate is None:
        return Check("escalation", "na")
    escalated = any(t.escalated for t in turns)
    ok = escalated == case.should_escalate
    return Check("escalation", "pass" if ok else "fail", f"escalated={escalated}")


def check_run(case: EvalCase, turns: Sequence[TurnResult]) -> tuple[Check, ...]:
    if len(turns) != len(case.turns):
        raise ValueError("one TurnResult per case turn")
    return (
        _tools(case, turns),
        _facts(case, turns),
        _must_not(case, turns),
        _outcome(case, turns),
        _escalation(case, turns),
    )


def run_passed(checks: Sequence[Check]) -> bool:
    """Passa quando nenhum check aplicável falha (tom e recusa pelo juiz ficam de fora)."""
    return all(c.status != "fail" for c in checks)
