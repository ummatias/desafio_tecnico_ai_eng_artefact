"""
escalate_to_human: abre um ticket com protocolo e prazo de retorno.

Prazo: 24 horas úteis a partir de agora, em horas de loja aberta, com feriados (§7.3, P-15).
"""

from datetime import date
from typing import Literal

from pydantic import Field

from emporio.tools.base import Tool, ToolArgs, ToolError, ToolResult
from emporio.tools.context import ToolContext
from emporio.tools.format import br_datetime
from emporio.tools.orders import owned_order

RETURN_BUSINESS_HOURS = 24


class EscalateArgs(ToolArgs):
    summary: str = Field(min_length=1, max_length=2000, description="Case summary for the team")
    category: Literal["complaint", "exchange", "order_delay", "other"]
    priority: Literal["normal", "high"] = "normal"
    order_id: int | None = Field(default=None, gt=0)
    stated_receipt_date: date | None = Field(
        default=None, description="Receipt date stated by the customer, if any"
    )


def escalate_to_human(args: EscalateArgs, ctx: ToolContext) -> ToolResult:
    if args.order_id is not None:
        owned_order(ctx, args.order_id)
    elif ctx.customer is None and args.category in ("exchange", "order_delay"):
        raise ToolError("customer_not_identified", "no customer is identified for this phone")
    due = ctx.calendar.add_business_hours(ctx.now, RETURN_BUSINESS_HOURS)
    ticket = ctx.tickets.create(
        customer_id=ctx.customer.customer_id if ctx.customer else None,
        order_id=args.order_id,
        category=args.category,
        priority=args.priority,
        summary=args.summary,
        stated_receipt_date=args.stated_receipt_date,
        created_at=ctx.now,
        due_at=due,
    )
    return {
        "protocol": ticket.protocol,
        "category": ticket.category,
        "priority": ticket.priority,
        "return_by": br_datetime(due),
        "note": "give the customer the protocol and the return deadline",
        "sections": ["7.3"],
        "assumptions": ["P-15"],
    }


ESCALATE_TO_HUMAN = Tool(
    name="escalate_to_human",
    description=(
        "Open a ticket for the human team (complaint, exchange, order delay, other). Returns "
        "the protocol number and the return deadline (24 business hours)."
    ),
    args_model=EscalateArgs,
    handler=escalate_to_human,
)
