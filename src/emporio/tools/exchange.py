"""
check_exchange: o motor do §4/§8 com a data de recebimento da fonte confiável (P-17).

A data informada pelo cliente só vai para o ticket (`stated_receipt_date`).
"""

from datetime import date
from typing import Any

from pydantic import Field

from emporio.domain.exchange import ExchangeRequest, Reason, evaluate
from emporio.tools.base import Tool, ToolArgs, ToolError, ToolResult
from emporio.tools.catalog import availability
from emporio.tools.context import ToolContext
from emporio.tools.format import br_date
from emporio.tools.orders import owned_order


class CheckExchangeArgs(ToolArgs):
    order_id: int = Field(gt=0)
    product_id: int = Field(gt=0, description="The item of the order")
    reason: Reason = Field(description="regret (§4.1), preference (§4.3) or defect (§4.2, §8)")
    stated_receipt_date: date | None = Field(
        default=None, description="Receipt date stated by the customer; only for the ticket"
    )
    custom_setup: bool | None = Field(default=None, description="§4.4 answer, if known")
    final_sale: bool | None = Field(default=None, description="§4.4 answer, if known")
    mouthpiece: bool | None = Field(default=None, description="§4.4 answer, wind instruments")
    replacement_product_id: int | None = Field(
        default=None, gt=0, description="Wanted product in a preference exchange"
    )


def _date(d: date | None) -> str | None:
    return br_date(d) if d is not None else None


def check_exchange(args: CheckExchangeArgs, ctx: ToolContext) -> ToolResult:
    order = owned_order(ctx, args.order_id)
    if args.product_id not in {item.product_id for item in order.items}:
        raise ToolError("product_not_in_order", f"product {args.product_id} is not in the order")
    product = ctx.catalog.get_product(args.product_id)
    if product is None:
        raise ToolError("not_found", f"product {args.product_id} not found")

    receipt = ctx.tracking.delivered_on(order.order_id, order.tracking_code)
    try:
        decision = evaluate(
            ExchangeRequest(
                order_id=order.order_id,
                order_date=order.order_date,
                order_status=order.status,
                category_id=product.category_id,
                reason=args.reason,
                today=ctx.today,
                receipt_date=receipt,
                stated_receipt_date=args.stated_receipt_date,
                custom_setup=args.custom_setup,
                final_sale=args.final_sale,
                mouthpiece=args.mouthpiece,
            )
        )
    except ValueError as exc:
        raise ToolError("invalid_request", str(exc)) from exc

    result: ToolResult = {
        "order_id": order.order_id,
        "product_id": product.product_id,
        "product_name": product.name,
        "reason": decision.reason,
        "outcome": decision.outcome,
        "code": decision.code,
        "route": decision.route,
        "basis": decision.basis,
        "receipt_date": _date(receipt),
        "deadline": _date(decision.deadline),
        "escalate": decision.escalate,
        "questions": list(decision.questions),
        "needs_stock": decision.needs_stock,
        "alternatives": list(decision.alternatives),
        "stated_receipt_date": _date(decision.stated_receipt_date),
        "sections": list(decision.sections),
        "assumptions": list(decision.assumptions),
    }
    if decision.needs_stock and args.replacement_product_id is not None:
        replacement = ctx.catalog.get_product(args.replacement_product_id)
        result["replacement"] = _replacement(args.replacement_product_id, replacement)
    return result


def _replacement(product_id: int, product: Any) -> dict[str, Any]:
    if product is None:
        return {"product_id": product_id, "availability": "not_found"}
    return {
        "product_id": product.product_id,
        "name": product.name,
        "availability": availability(product),
    }


CHECK_EXCHANGE = Tool(
    name="check_exchange",
    description=(
        "Return, exchange and warranty eligibility for one item of the customer's order. "
        "Outcomes: eligible, expired, not_eligible, to_confirm, ask, not_applicable."
    ),
    args_model=CheckExchangeArgs,
    handler=check_exchange,
)
