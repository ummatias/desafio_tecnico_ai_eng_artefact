"""
Totais do carrinho: promoções, PIX por item, frete, parcelas e pagamento combinado.

Estoque é verificado na tool.
Premissas: 
    - P-02
    - P-03
    - P-04
    - P-12
    - P-18
    - P-22
    - P-23
"""

import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from emporio.domain.installments import InstallmentPlan, installment_plans
from emporio.domain.pricing import pix_price, promotional_price

FREE_FREIGHT_FROM_CENTS = 50_000  # §5.1 "acima de R$ 500,00" (P-02)
FIXED_FREIGHT_CENTS = 3_500  # §5.1
COMBINED_PAYMENT_FROM_CENTS = 200_000  # §3.1 "acima de R$ 2.000,00" (P-02)
METRO_CITY = "campo grande"  # P-12

FreightRule = Literal["gratis", "taxa_fixa", "a_calcular"]


@dataclass(frozen=True)
class CartItem:
    product_id: int
    name: str
    list_price_cents: int  # preço de tabela
    quantity: int
    discount_percent: int | None = None  # promoção ativa


@dataclass(frozen=True)
class CartLine:
    item: CartItem
    unit_price_cents: int  # depois da promoção
    unit_pix_cents: int | None  # None: item promocional, sem PIX (P-04)

    @property
    def line_cents(self) -> int:
        """P-22: preço unitário já arredondado x quantidade."""
        return self.unit_price_cents * self.item.quantity

    @property
    def line_pix_cents(self) -> int:
        """No PIX; igual a `line_cents` se o item é promocional."""
        unit = self.unit_price_cents if self.unit_pix_cents is None else self.unit_pix_cents
        return unit * self.item.quantity


@dataclass(frozen=True)
class CartTotals:
    lines: list[CartLine]
    freight_cents: int | None
    freight_rule: FreightRule
    installments: list[InstallmentPlan]  # sobre total_cents (P-23)
    combined_payment_allowed: bool

    @property
    def subtotal_cents(self) -> int:
        """Depois das promoções, antes do PIX, sem frete: base da P-03."""
        return sum(line.line_cents for line in self.lines)

    @property
    def pix_subtotal_cents(self) -> int:
        return sum(line.line_pix_cents for line in self.lines)

    @property
    def total_cents(self) -> int:
        """Débito, boleto, crédito 1x. Sem frete se a calcular (P-18)."""
        return self.subtotal_cents + (self.freight_cents or 0)

    @property
    def total_pix_cents(self) -> int:
        """PIX nunca desconta o frete."""
        return self.pix_subtotal_cents + (self.freight_cents or 0)

    @property
    def frete_a_calcular(self) -> bool:
        """P-18: fora de Campo Grande o frete não tem valor; totais cobrem só os produtos."""
        return self.freight_cents is None


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(stripped.casefold().split())


def is_metro_region(city: str | None) -> bool:
    """P-12: "região metropolitana" = cidade Campo Grande."""
    return city is not None and _normalize(city) == METRO_CITY


def _line(item: CartItem) -> CartLine:
    if item.quantity < 1:
        raise ValueError(f"quantidade inválida para o produto {item.product_id}")
    # P-22: arredonda por unidade; as linhas só multiplicam.
    return CartLine(
        item=item,
        unit_price_cents=promotional_price(item.list_price_cents, item.discount_percent),
        unit_pix_cents=pix_price(
            item.list_price_cents, has_promotion=item.discount_percent is not None
        ),
    )


def _freight(subtotal_cents: int, city: str | None) -> tuple[int | None, FreightRule]:
    if not is_metro_region(city):
        return None, "a_calcular"  # P-18
    if subtotal_cents >= FREE_FREIGHT_FROM_CENTS:  # P-02, P-03
        return 0, "gratis"
    return FIXED_FREIGHT_CENTS, "taxa_fixa"


def cart_totals(items: Sequence[CartItem], city: str | None) -> CartTotals:
    if not items:
        raise ValueError("carrinho vazio")
    lines = [_line(item) for item in items]
    subtotal = sum(line.line_cents for line in lines)
    freight, rule = _freight(subtotal, city)
    return CartTotals(
        lines=lines,
        freight_cents=freight,
        freight_rule=rule,
        installments=installment_plans(subtotal + (freight or 0)),  # P-23: produtos + frete
        combined_payment_allowed=subtotal >= COMBINED_PAYMENT_FROM_CENTS,  # P-02, P-03
    )
