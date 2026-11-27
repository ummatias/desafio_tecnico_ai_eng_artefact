"""
CLI do agente: `emporio chat`.

O telefone simula o número verificado pelo canal (WhatsApp).
O histórico vive só na sessão do terminal

Na tela, `--debug` mostra os argumentos das tools sem máscara (uso local)
O trace gravado continua mascarado.
"""

import json
from collections.abc import Callable
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
from emporio.llm import LLMClient, LLMConfigError, Message, make_llm_client
from emporio.observability import TraceWriter
from emporio.repositories import Customer, CustomerRepository
from emporio.tools import build_context

EXIT_CONFIG = 2
ARGS_MAX_CHARS = 120
QUIT = "/sair"
CLEAR = "/limpar"

app = typer.Typer(no_args_is_help=True, add_completion=False, help="Agente da Empório da Música.")


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
