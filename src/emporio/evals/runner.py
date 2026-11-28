"""Executa os casos pelo agente real (`run_turn`), cada execução num banco novo."""

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from emporio.agent import TurnResult, run_turn
from emporio.config import Settings
from emporio.db.engine import make_engine
from emporio.db.seed import seed
from emporio.evals.cases import EvalCase
from emporio.evals.checks import Check, check_run, run_passed
from emporio.evals.judge import Judge, Verdict
from emporio.llm import LLMClient, Message
from emporio.observability import TraceWriter
from emporio.repositories import CustomerRepository
from emporio.tools import build_context

logger = logging.getLogger(__name__)

DEFAULT_RUNS = 3


@dataclass(frozen=True)
class RunRecord:
    case_id: str
    run_index: int
    turns: tuple[TurnResult, ...]
    checks: tuple[Check, ...]
    passed: bool
    verdict: Verdict | None = None
    error: str | None = None


@dataclass(frozen=True)
class SuiteResult:
    model: str
    runs_per_case: int
    cases: tuple[EvalCase, ...]
    records: tuple[RunRecord, ...] = field(default_factory=tuple)
    judge_model: str | None = None


def case_settings(base: Settings, case: EvalCase) -> Settings:
    return base.model_copy(
        update={
            "reference_date": case.reference_date,
            "tracking_source": case.session.tracking_source,
        }
    )


def run_case(
    case: EvalCase,
    base: Settings,
    llm: LLMClient,
    *,
    run_index: int = 1,
    tracer: TraceWriter | None = None,
    judge: Judge | None = None,
) -> RunRecord:
    settings = case_settings(base, case)
    engine = make_engine("sqlite://")
    try:
        seed(engine, settings.data_dir, settings.knowledge_dir)
        phone = case.session.phone
        customer = CustomerRepository(engine).get_by_phone(phone) if phone else None
        history: list[Message] = []
        turns: list[TurnResult] = []
        for turn in case.turns:
            ctx = build_context(settings, engine, customer)
            result = run_turn(
                llm, ctx, history, turn.user, tracer=tracer, session_id=f"{case.id}#{run_index}"
            )
            history.extend(result.transcript)
            turns.append(result)
    except Exception as exc:  # um caso quebrado não derruba a suíte
        logger.exception("case %s run %d failed", case.id, run_index)
        error = f"{type(exc).__name__}: {exc}"
        return RunRecord(case.id, run_index, (), (Check("run", "fail", error),), False, None, error)
    finally:
        engine.dispose()
    checks = check_run(case, turns)
    verdict = (
        judge.evaluate([(t.user, r.reply) for t, r in zip(case.turns, turns, strict=True)])
        if judge
        else None
    )
    return RunRecord(case.id, run_index, tuple(turns), checks, run_passed(checks), verdict)


def run_suite(
    cases: Sequence[EvalCase],
    settings: Settings,
    llm: LLMClient,
    *,
    runs: int = DEFAULT_RUNS,
    tracer: TraceWriter | None = None,
    judge: Judge | None = None,
    on_record: Callable[[RunRecord], None] | None = None,
) -> SuiteResult:
    records: list[RunRecord] = []
    for case in cases:
        for i in range(1, runs + 1):
            record = run_case(case, settings, llm, run_index=i, tracer=tracer, judge=judge)
            records.append(record)
            if on_record is not None:
                on_record(record)
    return SuiteResult(
        model=settings.llm_model,
        runs_per_case=runs,
        cases=tuple(cases),
        records=tuple(records),
        judge_model=judge.model if judge else None,
    )
