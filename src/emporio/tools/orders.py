"""
get_order: só pedidos do cliente da sessão (posse na query).

Pedido de outro cliente devolve `not_found`, igual a um inexistente. `order_value` é o valor
registrado no pedido, nunca "você pagou" (A04). A previsão de entrega é só estimativa.
"""

from typing import Any

from pydantic import Field

from emporio.domain.orders import delivery_status
from emporio.repositories import Customer, Order
from emporio.tools.base import Tool, ToolArgs, ToolError, ToolResult
from emporio.tools.context import ToolContext
from emporio.tools.format import br_date, brl, to_cents

ORDER_VALUE_NOTE = "order_value is the value recorded on the order; never say 'você pagou'"


def require_customer(ctx: ToolContext) -> Customer:
    if ctx.customer is None:
        raise ToolError("customer_not_identified", "no customer is identified for this phone")
    return ctx.customer


def owned_order(ctx: ToolContext, order_id: int) -> Order:
    customer = require_customer(ctx)
    order = ctx.orders.get_for_customer(order_id, customer.customer_id)
    if order is None:
        raise ToolError("not_found", f"order {order_id} not found for this customer")
    return order


def _order(order: Order, ctx: ToolContext) -> dict[str, Any]:
    status = delivery_status(
        status=order.status,
        order_date=order.order_date,
        estimated_delivery=order.estimated_delivery,
        today=ctx.today,
        calendar=ctx.calendar,
        stalled_after_business_days=ctx.stalled_after_business_days,
    )
    out: dict[str, Any] = {
        "order_id": order.order_id,
        "order_date": br_date(order.order_date),
        "status": order.status,
        "order_value": brl(to_cents(order.total)),
        "payment_method": order.payment_method,
        "installments": order.installments,
        "items": [
            {"product_id": i.product_id, "name": i.name, "quantity": i.quantity}
            for i in order.items
        ],
        "tracking_code": order.tracking_code,
        "delivery_estimate": br_date(order.estimated_delivery)
        if order.estimated_delivery
        else None,
        "delivery_state": status.state,
        "days_late": status.days_late,
        "business_days_open": status.business_days_open,
        "notes": order.notes,
    }
    if status.needs_attention:
        out["suggest_escalation"] = True
        out["priority"] = "high"
    return out


class GetOrderArgs(ToolArgs):
    order_id: int | None = Field(
        default=None, gt=0, description="Omit to list the customer's orders"
    )


def get_order(args: GetOrderArgs, ctx: ToolContext) -> ToolResult:
    meta: ToolResult = {
        "note": ORDER_VALUE_NOTE,
        "sections": ["5.1", "5.2", "5.3"],
        "assumptions": ["P-08"],
    }
    if args.order_id is not None:
        return {"order": _order(owned_order(ctx, args.order_id), ctx), **meta}
    customer = require_customer(ctx)
    orders = [_order(o, ctx) for o in ctx.orders.list_for_customer(customer.customer_id)]
    summary_keys = ("order_id", "order_date", "status", "order_value", "delivery_state")
    return {"orders": [{k: o[k] for k in summary_keys} for o in orders], **meta}


GET_ORDER = Tool(
    name="get_order",
    description=(
        "The identified customer's order: status, items, order value, tracking code, delivery "
        "estimate and delivery_state (on_time, late, stalled). Without order_id, lists orders."
    ),
    args_model=GetOrderArgs,
    handler=get_order,
)
