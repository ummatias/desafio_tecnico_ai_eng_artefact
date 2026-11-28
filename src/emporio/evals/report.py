"""
Relatório da suíte: o caso é a unidade.

Cada caso roda N vezes e vira `stable_pass` (todas passam), `stable_fail` (nenhuma) ou
`flaky`. As execuções nunca são somadas como tentativas independentes.
"""

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from emporio.evals.checks import CHECKS, Status
from emporio.evals.runner import RunRecord, SuiteResult
from emporio.evals.stats import percentile, wilson

CaseStatus = Literal["stable_pass", "flaky", "stable_fail"]
METRICS = (*CHECKS, "refusal", "tone")
METRIC_LABELS = {
    "tools": "Seleção de tools",
    "facts": "Fatos esperados",
    "must_not": "Nada proibido",
    "outcome": "Resultado da política",
    "escalation": "Escalada correta",
    "refusal": "Recusa correta (juiz)",
    "tone": "Tom (juiz)",
}
ESCALATION_TARGET = 0.25


def case_status(passes: Sequence[bool]) -> CaseStatus:
    if all(passes):
        return "stable_pass"
    if not any(passes):
        return "stable_fail"
    return "flaky"


def _run_metric(record: RunRecord, metric: str, should_refuse: bool | None) -> Status:
    if record.error:
        return "fail"
    if metric == "tone":
        passed = record.verdict.tone_passed if record.verdict else None
        return "na" if passed is None else ("pass" if passed else "fail")
    if metric == "refusal":
        refused = record.verdict.refused if record.verdict else None
        if should_refuse is None or refused is None:
            return "na"
        return "pass" if refused == should_refuse else "fail"
    for check in record.checks:
        if check.name == metric:
            return check.status
    return "na"


def _metric_status(statuses: Sequence[Status]) -> Status:
    applicable = [s for s in statuses if s != "na"]
    if not applicable:
        return "na"
    return "pass" if all(s == "pass" for s in applicable) else "fail"


def _costs(records: Sequence[RunRecord]) -> tuple[float, bool]:
    costs = [r.usage.cost_usd for rec in records for t in rec.turns for r in t.responses]
    return sum(c for c in costs if c is not None), all(c is not None for c in costs)


def _rate(k: int, n: int) -> dict[str, Any]:
    if n == 0:
        return {"k": 0, "n": 0, "rate": None, "ci95": None}
    low, high = wilson(k, n)
    return {"k": k, "n": n, "rate": k / n, "ci95": [low, high]}


def summarize(suite: SuiteResult) -> dict[str, Any]:
    by_case: dict[str, list[RunRecord]] = {c.id: [] for c in suite.cases}
    for record in suite.records:
        by_case[record.case_id].append(record)

    cases: list[dict[str, Any]] = []
    for case in suite.cases:
        records = by_case[case.id]
        metrics = {
            m: _metric_status([_run_metric(r, m, case.should_refuse) for r in records])
            for m in METRICS
        }
        escalated_runs = sum(any(t.escalated for t in r.turns) for r in records)
        cost, complete = _costs(records)
        failures = sorted(
            {
                f"{c.name}: {c.detail}" if c.detail else c.name
                for r in records
                for c in r.checks
                if c.status == "fail"
            }
        )
        cases.append(
            {
                "id": case.id,
                "category": case.category,
                "status": case_status([r.passed for r in records]),
                "passes": sum(r.passed for r in records),
                "runs": len(records),
                "metrics": metrics,
                "escalated_runs": escalated_runs,
                "escalated": escalated_runs * 2 > len(records),
                "cost_usd": cost if complete else None,
                "failures": failures,
                "judge_reasons": [r.verdict.reason for r in records if r.verdict],
            }
        )

    metric_rates = {
        m: _rate(
            sum(c["metrics"][m] == "pass" for c in cases),
            sum(c["metrics"][m] != "na" for c in cases),
        )
        for m in METRICS
    }
    turns = [t for r in suite.records for t in r.turns]
    latencies = [t.latency_ms for t in turns]
    responses = [resp for t in turns for resp in t.responses]
    total_cost, complete = _costs(suite.records)
    statuses = [c["status"] for c in cases]
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "model": suite.model,
        "judge_model": suite.judge_model,
        "runs_per_case": suite.runs_per_case,
        "n_cases": len(cases),
        "providers": sorted({r.provider for r in responses if r.provider}),
        "status_counts": {s: statuses.count(s) for s in ("stable_pass", "flaky", "stable_fail")},
        "pass_rate": _rate(statuses.count("stable_pass"), len(cases)),
        "metrics": metric_rates,
        "escalation_rate": {
            **_rate(sum(c["escalated"] for c in cases), len(cases)),
            "target": ESCALATION_TARGET,
        },
        "guard_trigger_rate": None,
        "cost_usd": {
            "total": total_cost if complete else None,
            "per_case_run": (total_cost / len(suite.records))
            if complete and suite.records
            else None,
        },
        "latency_ms": {
            "turn_p50": percentile(latencies, 50),
            "turn_p95": percentile(latencies, 95),
        },
        "tokens": {
            "prompt": sum(r.usage.prompt_tokens for r in responses),
            "completion": sum(r.usage.completion_tokens for r in responses),
            "reasoning": sum(r.usage.reasoning_tokens for r in responses),
        },
        "cases": cases,
    }


def _pct(rate: Mapping[str, Any]) -> str:
    if rate["rate"] is None:
        return "n/d"
    low, high = rate["ci95"]
    return f"{rate['rate']:.0%} ({rate['k']}/{rate['n']}; IC95 {low:.0%} a {high:.0%})"


def _money(value: float | None) -> str:
    return "n/d" if value is None else f"US$ {value:.4f}"


def _ms(value: float | None) -> str:
    return "n/d" if value is None else f"{value / 1000:.1f} s"


def render_markdown(summary: Mapping[str, Any]) -> str:
    counts = summary["status_counts"]
    esc = summary["escalation_rate"]
    lines = [
        f"# Avaliação · {summary['model']}",
        "",
        f"- Gerado em: {summary['generated_at']}",
        f"- Casos: {summary['n_cases']} · execuções por caso: {summary['runs_per_case']}",
        f"- Juiz de tom: {summary['judge_model'] or 'desligado (n/d)'}",
        f"- Providers: {', '.join(summary['providers']) or 'n/d'}",
        "",
        "## Resumo",
        "",
        f"- **Casos estáveis (todas as execuções passam):** {_pct(summary['pass_rate'])}",
        f"- stable_pass {counts['stable_pass']} · flaky {counts['flaky']} · "
        f"stable_fail {counts['stable_fail']}",
        f"- **Taxa de escalada:** {_pct(esc)} · meta ≤ {esc['target']:.0%}",
        "- Taxa de disparo do guard: n/d (o guard ainda não existe)",
        f"- Custo: total {_money(summary['cost_usd']['total'])} · por execução de caso "
        f"{_money(summary['cost_usd']['per_case_run'])}",
        f"- Latência por turno: p50 {_ms(summary['latency_ms']['turn_p50'])} · "
        f"p95 {_ms(summary['latency_ms']['turn_p95'])}",
        "",
        "| Métrica | Casos estáveis / aplicáveis |",
        "|---|---|",
        *(f"| {METRIC_LABELS[m]} | {_pct(r)} |" for m, r in summary["metrics"].items()),
        "",
        "Cada taxa conta casos, não execuções; IC95 de Wilson. Com poucos casos, o intervalo é "
        "largo: diferenças pequenas entre versões não são resultado.",
        "",
        "## Por caso",
        "",
        "| Caso | Categoria | Status | Passou | Falhas |",
        "|---|---|---|---|---|",
    ]
    for case in summary["cases"]:
        failures = "<br>".join(f.replace("|", "\\|") for f in case["failures"]) or "-"
        lines.append(
            f"| {case['id']} | {case['category']} | {case['status']} | "
            f"{case['passes']}/{case['runs']} | {failures} |"
        )
    return "\n".join(lines) + "\n"


def write_report(summary: Mapping[str, Any], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    results = out_dir / "results.json"
    report = out_dir / "report.md"
    results.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report.write_text(render_markdown(summary), encoding="utf-8")
    return results, report


def compare(a: Mapping[str, Any], b: Mapping[str, Any]) -> dict[str, list[str]]:
    """Casos que passam (stable_pass) só em A, só em B, nos dois ou em nenhum."""
    pass_a = {c["id"] for c in a["cases"] if c["status"] == "stable_pass"}
    pass_b = {c["id"] for c in b["cases"] if c["status"] == "stable_pass"}
    ids = sorted({c["id"] for c in a["cases"]} | {c["id"] for c in b["cases"]})
    return {
        "only_a": [i for i in ids if i in pass_a and i not in pass_b],
        "only_b": [i for i in ids if i in pass_b and i not in pass_a],
        "both": [i for i in ids if i in pass_a and i in pass_b],
        "neither": [i for i in ids if i not in pass_a and i not in pass_b],
    }
