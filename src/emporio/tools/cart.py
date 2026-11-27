"""
quote_cart: toda soma de dois ou mais preços passa por aqui (princípio 1).

A cidade vem do cliente da sessão. Produto em revisão entra com aviso na linha: o preço é
confiável, a identidade do produto não (D-42). Quantidade acima do estoque é erro, sem revelar o
número exato.
"""

from dataclasses import fields
from typing import Any

from pydantic import Field

from emporio.domain.cart import CartItem, CartTotals, cart_totals
from emporio.tools.base import Tool, ToolArgs, ToolError, ToolResult
from emporio.tools.catalog import UNDER_REVIEW_NOTE, availability
from emporio.tools.context import ToolContext
from emporio.tools.format import brl, to_cents


class CartLineArgs(ToolArgs):
    product_id: int = Field(gt=0)
    quantity: int = Field(default=1, ge=1, le=99)


class QuoteCartArgs(ToolArgs):
    items: list[CartLineArgs] = Field(min_length=1, max_length=20)


def _merge(lines: list[CartLineArgs]) -> dict[int, int]:
    merged: dict[int, int] = {}
    for line in lines:
        merged[line.product_id] = merged.get(line.product_id, 0) + line.quantity
    return merged


def _money(cents: int | None) -> str | None:
    return brl(cents) if cents is not None else None


def totals_result(totals: CartTotals, under_review: set[int]) -> dict[str, Any]:
    """Todos os campos e properties de `CartTotals`, sem o sufixo `_cents`."""
    lines = []
    for line in totals.lines:
        out: dict[str, Any] = {
            "product_id": line.item.product_id,
            "name": line.item.name,
            "quantity": line.item.quantity,
            "unit_price": brl(line.unit_price_cents),
            "unit_pix_price": _money(line.unit_pix_cents),
            "line_total": brl(line.line_cents),
            "line_pix_total": brl(line.line_pix_cents),
            "discount_percent": line.item.discount_percent,
        }
        if line.item.product_id in under_review:
            out["catalog_under_review"] = True
            out["note"] = UNDER_REVIEW_NOTE
        lines.append(out)
    return {
        "lines": lines,
        "subtotal": brl(totals.subtotal_cents),
        "pix_subtotal": brl(totals.pix_subtotal_cents),
        "freight": _money(totals.freight_cents),
        "freight_rule": totals.freight_rule,
        "freight_to_quote": totals.freight_to_quote,
        "total": brl(totals.total_cents),
        "total_pix": brl(totals.total_pix_cents),
        "installments": [
            {
                "n": plan.n,
                "first": brl(plan.first_cents),
                "other": brl(plan.other_cents),
                "total": brl(plan.total_cents),
            }
            for plan in totals.installments
        ],
        "combined_payment_allowed": totals.combined_payment_allowed,
    }


# Nomes que a saída precisa cobrir (testado)
CART_TOTALS_KEYS = frozenset(
    {f.name.removesuffix("_cents") for f in fields(CartTotals)}
    | {
        name.removesuffix("_cents")
        for name, value in vars(CartTotals).items()
        if isinstance(value, property)
    }
)


def quote_cart(args: QuoteCartArgs, ctx: ToolContext) -> ToolResult:
    items: list[CartItem] = []
    problems: list[dict[str, Any]] = []
    under_review: set[int] = set()
    for product_id, quantity in _merge(args.items).items():
        product = ctx.catalog.get_product(product_id)
        if product is None:
            problems.append({"product_id": product_id, "problem": "not_found"})
            continue
        state = availability(product)
        if state != "available":
            problems.append({"product_id": product_id, "problem": state})
            continue
        if quantity > product.stock_quantity:
            problems.append({"product_id": product_id, "problem": "insufficient_stock"})
            continue
        if product.inconsistent_listing:
            under_review.add(product_id)
        promotion = ctx.catalog.active_promotion(product_id)
        items.append(
            CartItem(
                product_id=product_id,
                name=product.name,
                list_price_cents=to_cents(product.price),
                quantity=quantity,
                discount_percent=promotion.discount_percent if promotion else None,
            )
        )
    if problems:
        raise ToolError(
            "invalid_items",
            "some items cannot be quoted; insufficient_stock means the requested quantity is "
            "not available (never state the stock number)",
            items=problems,
        )

    city = ctx.customer.city if ctx.customer else None
    totals = cart_totals(items, city)
    result: ToolResult = {"city": city, **totals_result(totals, under_review)}
    notes = []
    if totals.freight_to_quote:
        notes.append(
            "freight_to_quote: no freight value outside Campo Grande; totals cover products only "
            "(§5.2, P-18)"
        )
    if any(line.unit_pix_cents is None for line in totals.lines):
        notes.append("no PIX discount on promotional items (§6.2, P-04)")
    if notes:
        result["notes"] = notes
    result["sections"] = ["3", "3.1", "5.1", "5.2", "6.2"]
    result["assumptions"] = ["P-02", "P-03", "P-04", "P-05", "P-12", "P-18", "P-22", "P-23"]
    return result


QUOTE_CART = Tool(
    name="quote_cart",
    description=(
        "Totals for one or more items: promotions, PIX per item, freight for the customer's "
        "city, installment plans and combined payment. Use for every sum of prices."
    ),
    args_model=QuoteCartArgs,
    handler=quote_cart,
)
