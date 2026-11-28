"""
Um turno do agente: loop de tool calling limitado, com saída segura feita por código.

    1. Até `MAX_ITERATIONS` chamadas ao LLM com as 7 tools, cada saída de tool volta envelopada
    como dado.
    2. Iterações esgotadas, texto vazio ou texto com marcadores de controle do modelo: uma última
    chamada sem tools pede a resposta com o que as tools já devolveram (`forced_answer`). Uma
    resposta com marcadores (`<|start|>`, `<|channel|>`...) é inválida: a mesma chamada é repetida
    uma vez e, se persistir, segue para o passo seguinte. Ela nunca chega ao cliente.
    3. Se isso falhar, ou se o LLM falhar (`LLMError`), o código abre um chamado com
    `escalate_to_human` e responde com o protocolo. No máximo um chamado por turno.
"""

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from typing import Any, Literal

from emporio.agent.prompt import PROMPT_VERSION, build_system_prompt
from emporio.llm import LLMClient, LLMError, Message, Response, ToolSchema
from emporio.observability.masking import Masker
from emporio.observability.trace import TraceWriter
from emporio.tools import ToolContext, ToolResult, run_tool, tool_schemas

MAX_ITERATIONS = 5
ESCALATION_TOOL = "escalate_to_human"
SUMMARY_MAX_CHARS = 500

StopReason = Literal[
    "answer", "forced_answer", "max_iterations", "llm_error", "empty_answer", "invalid_answer"
]
# Marcadores do formato de chat do modelo (<|start|>, <|channel|>...), em qualquer posição: vazam
# como texto quando o provider não converte uma chamada de tool.
CONTROL_TOKENS = re.compile(r"<\|[a-z_]+\|>")

FORCED_ANSWER_INSTRUCTION = (
    "Limite de consultas deste turno atingido: não chame mais ferramentas. Responda ao cliente "
    "com o que as ferramentas já retornaram; se faltar informação, diga o que falta."
)
SAFE_REPLY_WITH_PROTOCOL = (
    "Desculpe, tive um problema para concluir seu atendimento por aqui. Já encaminhei para a "
    "nossa equipe: protocolo {protocol}, com retorno até {return_by}. 🙏"
)
SAFE_REPLY_WITHOUT_PROTOCOL = (
    "Desculpe, tive um problema para concluir seu atendimento por aqui. Nossa equipe vai "
    "continuar com você por este WhatsApp, (67) 3321-4500. 🙏"
)


@dataclass(frozen=True)
class ToolRun:
    name: str
    arguments: str
    result: ToolResult
    latency_ms: float
    by: Literal["model", "code"] = "model"
    # Escalada repetida no turno: a tool não rodou; volta o protocolo já aberto
    reused: bool = False

    @property
    def error(self) -> str | None:
        code = self.result.get("error")
        return str(code) if code is not None else None


@dataclass(frozen=True)
class TurnResult:
    reply: str
    stop_reason: StopReason
    iterations: int  # chamadas com tools (sem contar a chamada forçada)
    tool_runs: tuple[ToolRun, ...]
    responses: tuple[Response, ...]
    escalated: bool
    protocol: str | None
    llm_error: str | None
    latency_ms: float
    transcript: tuple[Message, Message]  # (cliente, resposta final) para o histórico
    invalid_responses: int = 0  # respostas descartadas por marcadores de controle


def wrap_tool_output(result: ToolResult) -> str:
    """
    Saída de tool como dado não confiável; o JSON mantém texto do banco dentro de strings.

    Sem o nome da tool no topo, o envelope não parece uma chamada para o modelo imitar; o
    `tool_call_id` da mensagem já liga o resultado à chamada.
    """
    return json.dumps(
        {"kind": "tool_result", "untrusted_data": True, "data": result},
        ensure_ascii=False,
        default=str,
    )


def _run(name: str, arguments: str, ctx: ToolContext, by: Literal["model", "code"]) -> ToolRun:
    started = perf_counter()
    result = run_tool(name, arguments, ctx)
    return ToolRun(name, arguments, result, (perf_counter() - started) * 1000, by)


def _escalation(runs: Sequence[ToolRun]) -> ToolRun | None:
    for run in runs:
        if run.name == ESCALATION_TOOL and run.error is None and "protocol" in run.result:
            return run
    return None


def _execute(name: str, arguments: str, ctx: ToolContext, runs: Sequence[ToolRun]) -> ToolRun:
    """Chamada do modelo. No máximo um chamado por turno: checado antes de rodar a tool."""
    if name == ESCALATION_TOOL:
        previous = _escalation(runs)
        if previous is not None:
            result = {
                **previous.result,
                "already_escalated": True,
                "note": "a ticket was already opened in this turn; give the customer this protocol",
            }
            return ToolRun(name, arguments, result, 0.0, by="model", reused=True)
    return _run(name, arguments, ctx, by="model")


def _invalid(response: Response) -> bool:
    return not response.tool_calls and bool(response.text and CONTROL_TOKENS.search(response.text))


def _text(response: Response) -> str | None:
    if response.tool_calls or response.text is None or _invalid(response):
        return None
    return response.text.strip() or None


def _complete(
    llm: LLMClient,
    messages: Sequence[Message],
    tools: Sequence[ToolSchema],
    responses: list[Response],
) -> tuple[Response, int]:
    response = llm.complete(messages, tools)
    responses.append(response)
    if not _invalid(response):
        return response, 0
    retry = llm.complete(messages, tools)
    responses.append(retry)
    return retry, 1


def _fallback(
    ctx: ToolContext, runs: list[ToolRun], stop: StopReason, user_text: str
) -> tuple[str, ToolRun | None]:
    escalation = _escalation(runs)
    if escalation is None:
        summary = (
            f"Atendimento automático interrompido ({stop}). "
            f"Última mensagem do cliente: {user_text[:SUMMARY_MAX_CHARS]}"
        )
        arguments = json.dumps({"summary": summary, "category": "other"}, ensure_ascii=False)
        run = _run(ESCALATION_TOOL, arguments, ctx, by="code")
        runs.append(run)
        escalation = _escalation([run])
    if escalation is None:
        return SAFE_REPLY_WITHOUT_PROTOCOL, None
    reply = SAFE_REPLY_WITH_PROTOCOL.format(
        protocol=escalation.result["protocol"], return_by=escalation.result.get("return_by", "")
    )
    return reply, escalation


def run_turn(
    llm: LLMClient,
    ctx: ToolContext,
    history: Sequence[Message],
    user_text: str,
    *,
    tracer: TraceWriter | None = None,
    session_id: str | None = None,
    max_iterations: int = MAX_ITERATIONS,
) -> TurnResult:
    started = perf_counter()
    schemas = tool_schemas()
    messages: list[Message] = [
        Message.system(build_system_prompt(ctx)),
        *history,
        Message.user(user_text),
    ]
    responses: list[Response] = []
    runs: list[ToolRun] = []
    reply: str | None = None
    stop: StopReason = "max_iterations"
    error: LLMError | None = None
    iterations = 0
    invalid = 0

    while iterations < max_iterations:
        iterations += 1
        try:
            response, retried = _complete(llm, messages, schemas, responses)
        except LLMError as exc:
            stop, error = "llm_error", exc
            break
        invalid += retried + _invalid(response)
        if response.tool_calls:
            messages.append(response.as_message())
            for call in response.tool_calls:
                run = _execute(call.name, call.arguments, ctx, runs)
                runs.append(run)
                messages.append(Message.tool(call.id, wrap_tool_output(run.result)))
            continue
        reply = _text(response)
        if reply is not None:
            stop = "answer"
        else:
            stop = "invalid_answer" if _invalid(response) else "empty_answer"
        break

    if reply is None and stop in ("max_iterations", "empty_answer", "invalid_answer"):
        forced_messages = [*messages, Message.system(FORCED_ANSWER_INSTRUCTION)]
        try:
            forced, retried = _complete(llm, forced_messages, [], responses)
        except LLMError as exc:
            error = exc
        else:
            invalid += retried + _invalid(forced)
            reply = _text(forced)
            if reply is not None:
                stop = "forced_answer"

    escalation = _escalation(runs)
    if reply is None:
        reply, escalation = _fallback(ctx, runs, stop, user_text)

    result = TurnResult(
        reply=reply,
        stop_reason=stop,
        iterations=iterations,
        tool_runs=tuple(runs),
        responses=tuple(responses),
        escalated=escalation is not None,
        protocol=str(escalation.result["protocol"]) if escalation else None,
        llm_error=type(error).__name__ if error else None,
        latency_ms=(perf_counter() - started) * 1000,
        transcript=(Message.user(user_text), Message("assistant", reply)),
        invalid_responses=invalid,
    )
    if tracer is not None:
        tracer.write(trace_record(result, ctx, user_text, session_id))
    return result


def _args(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def trace_record(
    result: TurnResult, ctx: ToolContext, user_text: str, session_id: str | None
) -> dict[str, Any]:
    """Registro do turno, já mascarado. Saídas de tool não entram."""
    mask = Masker(ctx.customer)
    responses = result.responses
    costs = [r.usage.cost_usd for r in responses]
    return {
        "ts": datetime.now(UTC).isoformat(),
        "session_id": mask.text(session_id) if session_id is not None else None,
        "prompt_version": PROMPT_VERSION,
        "now": ctx.now.isoformat(),
        "customer_identified": ctx.customer is not None,
        "models": sorted({r.model for r in responses if r.model}),
        "providers": sorted({r.provider for r in responses if r.provider}),
        "generation_ids": [r.generation_id for r in responses if r.generation_id],
        # Provider de cada chamada, na ordem (a lista acima é só o conjunto).
        "call_providers": [r.provider for r in responses],
        "iterations": result.iterations,
        "llm_calls": len(responses),
        "stop_reason": result.stop_reason,
        "invalid_responses": result.invalid_responses,
        "llm_error": result.llm_error,
        "tools": [
            {
                "name": run.name,
                "by": run.by,
                "reused": run.reused,
                "args": mask.value(_args(run.arguments)),
                "error": run.error,
                "latency_ms": round(run.latency_ms, 1),
            }
            for run in result.tool_runs
        ],
        "escalated": result.escalated,
        "protocol": result.protocol,
        "tokens": {
            "prompt": sum(r.usage.prompt_tokens for r in responses),
            "completion": sum(r.usage.completion_tokens for r in responses),
            "reasoning": sum(r.usage.reasoning_tokens for r in responses),
            "cached": sum(r.usage.cached_tokens for r in responses),
        },
        "cost_usd": sum(c for c in costs if c is not None)
        if costs and all(c is not None for c in costs)
        else None,
        "latency_ms": round(result.latency_ms, 1),
        "llm_latency_ms": round(sum(r.latency_ms for r in responses), 1),
        "user_text": mask.text(user_text),
        "reply": mask.text(result.reply),
    }
