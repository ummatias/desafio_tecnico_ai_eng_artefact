"""
System prompt versionado.

O texto fica em `prompts/system_<versão>.md`

Tudo o que depende do turno (agora, estado da loja, agenda, cliente) 
é calculado por código e injetado aqui.
"""

from datetime import date, time, timedelta
from functools import cache
from importlib.resources import files
from string import Template

from emporio.domain.calendar import StoreCalendar
from emporio.repositories import Customer
from emporio.tools.context import ToolContext
from emporio.tools.format import br_date, weekday_name

PROMPT_VERSION = "v1"
AGENDA_DAYS = 7


@cache
def _template(version: str) -> Template:
    text = files("emporio.agent").joinpath("prompts", f"system_{version}.md").read_text("utf-8")
    return Template(text)


def _hhmm(t: time) -> str:
    return f"{t:%H:%M}"


def _when(d: date, today: date) -> str:
    label = f"{weekday_name(d)}, {br_date(d)}"
    if d == today:
        return f"hoje ({label})"
    if d == today + timedelta(days=1):
        return f"amanhã ({label})"
    return label


def _day_line(calendar: StoreCalendar, d: date, today: date) -> str:
    hours = calendar.opening_hours(d)
    holiday = calendar.holiday_name(d)
    if hours is None:
        status = f"fechada (feriado: {holiday})" if holiday else "fechada"
    else:
        status = f"aberta das {_hhmm(hours[0])} às {_hhmm(hours[1])}"
    names = [n.name for n in calendar.notices(d)]
    extra = f" · data especial: {', '.join(names)}" if names else ""
    return f"- {_when(d, today)}: {status}{extra}"


def _agenda(ctx: ToolContext) -> str:
    today = ctx.today
    return "\n".join(
        _day_line(ctx.calendar, today + timedelta(days=i), today) for i in range(AGENDA_DAYS)
    )


def _store_status(ctx: ToolContext) -> str:
    status = ctx.calendar.store_status(ctx.now)
    if status.is_open and status.closes_at is not None:
        return f"aberta, fecha às {_hhmm(status.closes_at.time())}."
    reopen = status.next_opening
    if reopen is None:
        return "fechada."
    when = _when(reopen.date(), ctx.today)
    reason = f" ({status.holiday_name})" if status.holiday_name else ""
    return f"fechada{reason}; reabre {when} às {_hhmm(reopen.time())}."


def _notices(ctx: ToolContext) -> str:
    notices = ctx.calendar.notices(ctx.today)
    if not notices:
        return ""
    lines = [f"- Hoje: {n.name} ({n.assumption})." for n in notices]
    return "\n".join(lines) + "\n"


def _customer(customer: Customer | None) -> str:
    if customer is None:
        return (
            "- Não identificado pelo telefone. Pedidos, trocas e chamados de pedido exigem um "
            "cliente identificado: peça para falar pelo número cadastrado na compra."
        )
    first = customer.name.split()[0]
    return f"- Primeiro nome: {first}. Cidade de cadastro: {customer.city}."


def build_system_prompt(ctx: ToolContext, version: str = PROMPT_VERSION) -> str:
    return _template(version).substitute(
        customer=_customer(ctx.customer),
        now=f"{weekday_name(ctx.today)}, {br_date(ctx.today)}, "
        f"{_hhmm(ctx.now.astimezone(ctx.calendar.tz).time())}",
        store_status=_store_status(ctx),
        notices=_notices(ctx),
        agenda=_agenda(ctx),
    )
