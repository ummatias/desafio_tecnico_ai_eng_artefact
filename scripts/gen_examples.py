"""
Gera as conversas de exemplo com o agente real: `uv run python scripts/gen_examples.py`.

Cada roteiro em `examples/scripts/` (formato dos casos de eval) roda uma vez, num banco novo, e
vira `examples/<id>.md`. A saída não é editada.
"""

import sys
from pathlib import Path

from emporio.agent import PROMPT_VERSION
from emporio.config import Settings
from emporio.evals.cases import load_cases
from emporio.evals.runner import case_settings, run_case
from emporio.llm import make_llm_client

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    settings = Settings()
    llm = make_llm_client(settings)
    for case in load_cases(ROOT / "examples" / "scripts"):
        record = run_case(case, settings, llm)
        if record.error:
            print(f"{case.id}: {record.error}", file=sys.stderr)
            return 1
        s = case_settings(settings, case)
        providers = sorted({r.provider for t in record.turns for r in t.responses if r.provider})
        costs = [r.usage.cost_usd for t in record.turns for r in t.responses]
        cost = f"US$ {sum(c for c in costs if c is not None):.4f}" if all(costs) else "n/d"
        tracking = (
            "fixture sintética de rastreio (`fixtures/delivery_events.csv`)"
            if s.tracking_source == "fixture"
            else "nenhum rastreio (`none`)"
        )
        lines = [
            f"# {case.id}",
            "",
            f"- REFERENCE_DATE: {s.reference_date:%Y-%m-%d %H:%M}",
            f"- TRACKING_SOURCE: {tracking}",
            f"- Cliente (telefone): {case.session.phone or 'não identificado'}",
            f"- Modelo: {s.llm_model} · provider: {', '.join(providers) or 'n/d'}"
            f" · temperatura: {s.llm_temperature}",
            f"- Prompt: {PROMPT_VERSION}",
            f"- Custo: {cost}",
            "- Saída gerada pelo agente, sem edição.",
            "",
        ]
        for turn_case, turn in zip(case.turns, record.turns, strict=True):
            tools = ", ".join(f"`{r.name}`" for r in turn.tool_runs) or "nenhuma"
            lines += [
                f"**Cliente:** {turn_case.user}",
                "",
                f"*Tools: {tools}*",
                "",
                f"**Agente:** {turn.reply}",
                "",
            ]
        out = ROOT / "examples" / f"{case.id}.md"
        out.write_text("\n".join(lines), encoding="utf-8")
        print(f"{out.relative_to(ROOT)} ({cost})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
