"""
search_products e get_product.

- Preço de venda já com a promoção ativa; PIX só sem promoção (P-04); descontos truncados (P-22).
- Campanha do §6.1 só vale com promoção ativa no sistema (P-19).
- Produto com cadastro inconsistente (135-144) nunca entra na lista principal: vai para
  `under_review`, e o get_product oculta descrição e specs (princípio 3).
- O número exato de estoque nunca é exposto.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal

from pydantic import Field
from rapidfuzz import fuzz

from emporio.db.derived import normalize_name
from emporio.domain.installments import installment_plans
from emporio.domain.pricing import pix_price, promotional_price
from emporio.repositories import Category, Product, Promotion
from emporio.tools.base import Tool, ToolArgs, ToolError, ToolResult
from emporio.tools.context import ToolContext
from emporio.tools.format import brl, to_cents

Availability = Literal["available", "out_of_stock", "discontinued", "coming_soon"]

NAME_MATCH_THRESHOLD = 85
CATEGORY_MATCH_THRESHOLD = 80
UNDER_REVIEW_NOTE = "catalog under review: do not confirm or deny this product; offer the team"
# Palavras de categoria ambíguas: "cordas" (de guitarra, acessório) e "instrumentos" (qualquer um).
AMBIGUOUS_CATEGORY_WORDS = frozenset({"cordas", "instrumentos"})


def availability(product: Product) -> Availability:
    if product.status == "discontinued":
        return "discontinued"
    if product.status == "coming_soon":
        return "coming_soon"
    return "available" if product.stock_quantity > 0 else "out_of_stock"


@dataclass(frozen=True)
class Prices:
    list_cents: int
    sale_cents: int
    pix_cents: int | None
    promotion: Promotion | None


def prices(product: Product, promotion: Promotion | None) -> Prices:
    list_cents = to_cents(product.price)
    percent = promotion.discount_percent if promotion else None
    return Prices(
        list_cents=list_cents,
        sale_cents=promotional_price(list_cents, percent),
        pix_cents=pix_price(list_cents, has_promotion=promotion is not None),
        promotion=promotion,
    )


def _summary(product: Product, p: Prices) -> dict[str, Any]:
    out: dict[str, Any] = {
        "product_id": product.product_id,
        "name": product.name,
        "category": product.category_name,
        "price": brl(p.sale_cents),
        "pix_price": brl(p.pix_cents) if p.pix_cents is not None else None,
        "availability": availability(product),
    }
    if p.promotion is not None:
        out["list_price"] = brl(p.list_cents)
        out["discount_percent"] = p.promotion.discount_percent
    return out


def _under_review(product: Product) -> dict[str, Any]:
    return {"product_id": product.product_id, "name": product.name, "note": UNDER_REVIEW_NOTE}


# search_products


class SearchProductsArgs(ToolArgs):
    query: str | None = Field(
        default=None, max_length=100, description="Model, brand or name, e.g. 'takamine gd 20'"
    )
    category: str | None = Field(
        default=None,
        max_length=60,
        description="Category name in Portuguese (e.g. 'violões', 'guitarras', 'sopro') or id",
    )
    min_price: Decimal | None = Field(default=None, ge=0, description="In BRL, on the sale price")
    max_price: Decimal | None = Field(default=None, gt=0, description="In BRL, on the sale price")
    strings_type: Literal["nylon", "steel"] | None = None
    is_electric: bool | None = None
    include_unavailable: bool = Field(
        default=False, description="Also list out-of-stock and discontinued items"
    )
    limit: int = Field(default=10, ge=1, le=20)


def _match_categories(term: str, categories: list[Category]) -> list[Category]:
    if term.strip().isdigit():
        found = [c for c in categories if c.category_id == int(term)]
    else:
        wanted = normalize_name(term)
        found = [
            c
            for c in categories
            if fuzz.WRatio(wanted, normalize_name(c.name)) >= CATEGORY_MATCH_THRESHOLD
        ]
    if not found:
        valid = [f"{c.category_id} {c.name}" for c in categories]
        raise ToolError("unknown_category", f"no category matches {term!r}", categories=valid)
    return found


def _name_score(query: str, product: Product) -> float:
    compact = query.replace(" ", "")
    name = product.normalized_name
    score = fuzz.token_set_ratio(query, name)
    if len(compact) >= 4:
        # "gd 20" x "gd20": compara também sem espaços
        score = max(score, fuzz.partial_ratio(compact, name.replace(" ", "")))
    return score


def _singular(word: str) -> str:
    if word.endswith("oes"):
        return word[:-3] + "ao"  # violoes -> violao
    return word.removesuffix("s")


def _category_words(categories: list[Category]) -> dict[str, set[int]]:
    """
    Primeira palavra do nome de cada categoria, no plural e no singular ("ukuleles", "ukulele").

    O nome do produto não traz a categoria ("Kala KA-C Concert Mogno"), então "ukulele kala ka-c"
    não casava com nada.
    """
    words: dict[str, set[int]] = {}
    for category in categories:
        first = normalize_name(category.name).split()[0]
        if first in AMBIGUOUS_CATEGORY_WORDS:
            continue
        for word in (first, _singular(first)):
            words.setdefault(word, set()).add(category.category_id)
    return words


def _split_category_words(query: str, words: dict[str, set[int]]) -> tuple[str, set[int]]:
    """Separa da busca as palavras que nomeiam uma categoria."""
    rest: list[str] = []
    named: set[int] = set()
    for token in query.split():
        if token in words:
            named |= words[token]
        else:
            rest.append(token)
    return " ".join(rest), named


def _description_hit(query: str, product: Product) -> bool:
    description = normalize_name(product.description or "")
    return all(token in description.split() for token in query.split())


def search_products(args: SearchProductsArgs, ctx: ToolContext) -> ToolResult:
    categories = ctx.catalog.list_categories()
    selected = _match_categories(args.category, categories) if args.category else []
    products = [
        p
        for p in ctx.catalog.list_products(
            strings_type=args.strings_type, is_electric=args.is_electric, available_only=False
        )
        if not selected or p.category_id in {c.category_id for c in selected}
    ]
    query = normalize_name(args.query) if args.query else ""
    if query:
        rest, named = _split_category_words(query, _category_words(categories))

        def score(product: Product) -> float:
            # Com a palavra da categoria, o produto dessa categoria é comparado sem ela; o
            # resultado só pode subir, então nenhuma busca que já achava algo deixa de achar.
            base = _name_score(query, product)
            if product.category_id in named:
                return max(base, _name_score(rest, product) if rest else 100.0)
            return base

        scored = [(score(p), p) for p in products]
        products = [
            p
            for score, p in sorted(scored, key=lambda sp: -sp[0])
            if score >= NAME_MATCH_THRESHOLD
            or (p.inconsistent_listing and _description_hit(query, p))
        ]

    promotions = ctx.catalog.active_promotions()
    min_cents = to_cents(args.min_price) if args.min_price is not None else None
    max_cents = to_cents(args.max_price) if args.max_price is not None else None
    main: list[dict[str, Any]] = []
    with_pix: list[dict[str, Any]] = []
    unavailable: list[dict[str, Any]] = []
    under_review: list[dict[str, Any]] = []
    for product in products:
        p = prices(product, promotions.get(product.product_id))
        if min_cents is not None and p.sale_cents < min_cents:
            continue
        within = max_cents is None or p.sale_cents <= max_cents
        if product.inconsistent_listing:
            if within:
                under_review.append(_under_review(product))
        elif availability(product) != "available":
            if within and (query or args.include_unavailable):
                unavailable.append(_summary(product, p))
        elif within:
            main.append(_summary(product, p))
        elif max_cents is not None and p.pix_cents is not None and p.pix_cents <= max_cents:
            with_pix.append(_summary(product, p))

    result: ToolResult = {
        "products": main[: args.limit],
        "total_products": len(main),
        "within_budget_with_pix": with_pix[: args.limit],
        "unavailable": unavailable[: args.limit],
        "under_review": under_review,
        "sections": ["6.2", "7.3"],
        "assumptions": ["P-04", "P-19", "P-22"],
    }
    notes = []
    empty = [c.name for c in selected if c.product_count == 0]
    if empty:
        notes.append(f"empty_category: {', '.join(empty)} has no products in the catalog")
    if with_pix:
        notes.append("within_budget_with_pix: above the budget, within it only by PIX")
    if unavailable:
        notes.append("unavailable: say so and suggest available alternatives (§7.3)")
    if notes:
        result["notes"] = notes
    return result


# get_product


class GetProductArgs(ToolArgs):
    product_id: int = Field(gt=0)


def get_product(args: GetProductArgs, ctx: ToolContext) -> ToolResult:
    product = ctx.catalog.get_product(args.product_id)
    if product is None:
        raise ToolError("not_found", f"product {args.product_id} not found")
    p = prices(product, ctx.catalog.active_promotion(product.product_id))
    result: ToolResult = {
        "product_id": product.product_id,
        "name": product.name,
        "category": product.category_name,
        "availability": availability(product),
        "price": brl(p.sale_cents),
        "promotion": None,
        "pix_price": brl(p.pix_cents) if p.pix_cents is not None else None,
        "installments": [
            {
                "n": plan.n,
                "first": brl(plan.first_cents),
                "other": brl(plan.other_cents),
                "total": brl(plan.total_cents),
            }
            for plan in installment_plans(p.sale_cents)
        ],
        "catalog_under_review": product.inconsistent_listing,
        "sections": ["3", "3.1", "6.2"],
        "assumptions": ["P-04", "P-05", "P-06", "P-07", "P-19", "P-22"],
    }
    if p.promotion is not None:
        result["promotion"] = {
            "description": p.promotion.description,
            "discount_percent": p.promotion.discount_percent,
            "original_price": brl(p.list_cents),
            "promotional_price": brl(p.sale_cents),
        }
        result["pix_note"] = "no PIX discount on promotional prices (§6.2)"
    if product.inconsistent_listing:
        result["note"] = UNDER_REVIEW_NOTE
    else:
        result["description"] = product.description
        result["specs"] = product.specs
    return result


SEARCH_PRODUCTS = Tool(
    name="search_products",
    description=(
        "Search the catalog by name (fuzzy) and filters. Only available items in 'products'; "
        "prices already include active promotions. Use for any product or budget question."
    ),
    args_model=SearchProductsArgs,
    handler=search_products,
)

GET_PRODUCT = Tool(
    name="get_product",
    description=(
        "Details of one product: price, active promotion, PIX price, valid installment plans, "
        "availability, description and specs."
    ),
    args_model=GetProductArgs,
    handler=get_product,
)
