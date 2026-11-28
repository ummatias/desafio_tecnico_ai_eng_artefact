"""
CLI do agente: `emporio chat` e `emporio eval run|compare`.

O telefone simula o número verificado pelo canal (WhatsApp).
O histórico vive só na sessão do terminal

Na tela, `--debug` mostra os argumentos das tools sem máscara (uso local)
O trace gravado continua mascarado.
"""

import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from uuid import uuid4

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from sqlalchemy import Engine

from emporio.agent import PROMPT_VERSION, TurnResult, run_turn
from emporio.config import Settings, get_settings
from emporio.db.engine import make_engine
from emporio.db.seed import seed
from emporio.evals.cases import CaseError, load_cases
from emporio.evals.judge import JudgeConfigError, make_judge
from emporio.evals.report import compare, render_markdown, summarize, write_report
from emporio.evals.runner import DEFAULT_RUNS, RunRecord, run_suite
from emporio.llm import LLMClient, LLMConfigError, Message, make_llm_client
from emporio.observability import TraceWriter
from emporio.repositories import Customer, CustomerRepository
from emporio.tools import build_context

EXIT_CONFIG = 2
ARGS_MAX_CHARS = 120
QUIT = "/sair"
CLEAR = "/limpar"

app = typer.Typer(no_args_is_help=True, add_completion=False, help="Agente da Empório da Música.")
eval_app = typer.Typer(no_args_is_help=True, help="Avaliação do agente com casos YAML.")
app.add_typer(eval_app, name="eval")


@app.callback()
def _main() -> None:
    """Agente de atendimento da Empório da Música."""


def _customer_label(customer: Customer | None) -> str:
    if customer is None:
        return "não identificado"
    return f"{customer.name.split()[0]} ({customer.city})"


def _banner(
    settings: Settings, customer: Customer | None, tracer: TraceWriter | None, session_id: str
) -> Panel:
    ref = settings.reference_date
    lines = [
        f"Modelo: {settings.llm_model} · prompt {PROMPT_VERSION}",
        f"REFERENCE_DATE: {f'{ref:%d/%m/%Y %H:%M}' if ref else 'relógio real'}",
        f"TRACKING_SOURCE: {settings.tracking_source}",
        f"Cliente: {_customer_label(customer)}",
        f"Trace: {tracer.path if tracer else 'desligado'} · sessão {session_id}",
        f"Comandos: {CLEAR} zera o histórico, {QUIT} (ou Ctrl-D) encerra.",
    ]
    return Panel(Text("\n".join(lines)), title="Empório da Música · chat", expand=False)


def _compact(raw: str) -> str:
    try:
        text = json.dumps(json.loads(raw), ensure_ascii=False, separators=(",", ":"))
    except json.JSONDecodeError:
        text = raw
    return text if len(text) <= ARGS_MAX_CHARS else text[: ARGS_MAX_CHARS - 1] + "…"


def _debug(console: Console, result: TurnResult) -> None:
    if result.tool_runs:
        table = Table(
            "tool", "argumentos", "erro", "by", "reused", title="tools", title_justify="left"
        )
        for run in result.tool_runs:
            table.add_row(
                Text(run.name),
                Text(_compact(run.arguments)),
                Text(run.error or "-"),
                Text(run.by),
                Text("sim" if run.reused else "-"),
            )
        console.print(table)
    responses = result.responses
    costs = [r.usage.cost_usd for r in responses]
    cost = (
        f"US$ {sum(c for c in costs if c is not None):.6f}"
        if costs and all(c is not None for c in costs)
        else "n/d"
    )
    providers = ", ".join(sorted({r.provider for r in responses if r.provider})) or "n/d"
    summary = (
        f"stop_reason={result.stop_reason} · iterações={result.iterations} · "
        f"chamadas={len(responses)} · tokens prompt/completion/reasoning="
        f"{sum(r.usage.prompt_tokens for r in responses)}/"
        f"{sum(r.usage.completion_tokens for r in responses)}/"
        f"{sum(r.usage.reasoning_tokens for r in responses)} · custo={cost} · "
        f"latência={result.latency_ms:.0f} ms · provider={providers}"
    )
    if result.llm_error:
        summary += f" · erro={result.llm_error}"
    console.print(Text(summary, style="dim"))


def run_chat(
    settings: Settings,
    engine: Engine,
    console: Console,
    read_line: Callable[[str], str],
    *,
    llm_factory: Callable[[Settings], LLMClient] = make_llm_client,
    phone: str | None = None,
    debug: bool = False,
    session_id: str | None = None,
) -> int:
    """Conversa no terminal. Devolve o código de saída."""
    seed(engine, settings.data_dir, settings.knowledge_dir)
    customer = CustomerRepository(engine).get_by_phone(phone) if phone else None
    if phone and customer is None:
        console.print(
            Text("Telefone não cadastrado: seguindo como cliente não identificado.", style="yellow")
        )
    try:
        llm = llm_factory(settings)
    except LLMConfigError as exc:
        console.print(Text(f"{exc}. Defina LLM_API_KEY no .env.", style="red"))
        return EXIT_CONFIG
    tracer = TraceWriter.from_settings(settings)
    session = session_id or uuid4().hex[:12]
    console.print(_banner(settings, customer, tracer, session))

    history: list[Message] = []
    while True:
        try:
            line = read_line("você> ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print()
            return 0
        if not line:
            continue
        if line == QUIT:
            return 0
        if line == CLEAR:
            history.clear()
            console.print(Text("Histórico zerado.", style="dim"))
            continue
        ctx = build_context(settings, engine, customer)
        result = run_turn(llm, ctx, history, line, tracer=tracer, session_id=session)
        history.extend(result.transcript)
        console.print(Text.assemble(("Empório: ", "bold green"), result.reply))
        if debug:
            _debug(console, result)


@app.command()
def chat(
    phone: Annotated[
        str | None, typer.Option(help="Telefone do cliente, como verificado pelo canal.")
    ] = None,
    debug: Annotated[bool, typer.Option(help="Mostra tools, tokens, custo e latência.")] = False,
    session_id: Annotated[str | None, typer.Option(help="Id da sessão no trace.")] = None,
) -> None:
    """Conversa com o agente no terminal."""
    settings = get_settings()
    console = Console(highlight=False)
    code = run_chat(
        settings,
        make_engine(settings.database_url),
        console,
        console.input,
        llm_factory=make_llm_client,
        phone=phone,
        debug=debug,
        session_id=session_id,
    )
    raise typer.Exit(code)


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9.-]+", "_", text).strip("_")


def run_evals(
    settings: Settings,
    console: Console,
    *,
    cases_dir: Path,
    runs: int = DEFAULT_RUNS,
    only: set[str] | None = None,
    out_dir: Path = Path("var/evals"),
    report_path: Path | None = None,
    llm_factory: Callable[[Settings], LLMClient] = make_llm_client,
) -> int:
    """Roda a suíte e grava `results.json`, `report.md` e `traces.jsonl`."""
    try:
        cases = load_cases(cases_dir, only)
        llm = llm_factory(settings)
        judge = make_judge(settings, llm_factory)
    except (CaseError, JudgeConfigError) as exc:
        console.print(Text(str(exc), style="red"))
        return EXIT_CONFIG
    except LLMConfigError as exc:
        console.print(Text(f"{exc}. Defina LLM_API_KEY no .env.", style="red"))
        return EXIT_CONFIG

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    target = out_dir / f"{stamp}-{_slug(settings.llm_model)}"
    tracer = TraceWriter(target / "traces.jsonl")
    console.print(
        Text(
            f"{len(cases)} casos, {runs} execuções cada · modelo {settings.llm_model} · "
            f"juiz {judge.model if judge else 'desligado'}"
        )
    )

    def progress(record: RunRecord) -> None:
        status = "pass" if record.passed else "FAIL"
        console.print(Text(f"  {record.case_id} #{record.run_index}: {status}"))

    suite = run_suite(
        cases, settings, llm, runs=runs, tracer=tracer, judge=judge, on_record=progress
    )
    summary = summarize(suite)
    results, report = write_report(summary, target)
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(render_markdown(summary), encoding="utf-8")
    counts = summary["status_counts"]
    console.print(
        Text(
            f"stable_pass {counts['stable_pass']} · flaky {counts['flaky']} · "
            f"stable_fail {counts['stable_fail']} · relatório: {report}"
        )
    )
    console.print(Text(f"resultados: {results}", style="dim"))
    return 0


@eval_app.command("run")
def eval_run(
    cases: Annotated[Path, typer.Option(help="Pasta dos casos YAML.")] = Path("evals/cases"),
    runs: Annotated[int, typer.Option(min=1, help="Execuções por caso.")] = DEFAULT_RUNS,
    only: Annotated[
        str | None, typer.Option(help="Ids separados por vírgula (ex.: produto-gd20).")
    ] = None,
    out: Annotated[Path, typer.Option(help="Pasta das saídas.")] = Path("var/evals"),
    report: Annotated[
        Path | None, typer.Option(help="Também grava o relatório markdown neste caminho.")
    ] = None,
) -> None:
    """Roda os casos pelo agente real e grava o relatório."""
    selected = {i.strip() for i in only.split(",") if i.strip()} if only else None
    code = run_evals(
        get_settings(),
        Console(highlight=False),
        cases_dir=cases,
        runs=runs,
        only=selected,
        out_dir=out,
        report_path=report,
        llm_factory=make_llm_client,
    )
    raise typer.Exit(code)


@eval_app.command("compare")
def eval_compare(
    a: Annotated[Path, typer.Argument(help="results.json da versão A.")],
    b: Annotated[Path, typer.Argument(help="results.json da versão B.")],
) -> None:
    """Lista os casos que passam (stable_pass) só em A, só em B, nos dois ou em nenhum."""
    console = Console(highlight=False)
    buckets = compare(
        json.loads(a.read_text(encoding="utf-8")), json.loads(b.read_text(encoding="utf-8"))
    )
    labels = {"only_a": "só A", "only_b": "só B", "both": "os dois", "neither": "nenhum"}
    for key, label in labels.items():
        ids = ", ".join(buckets[key]) or "-"
        console.print(Text(f"{label} ({len(buckets[key])}): {ids}"))
