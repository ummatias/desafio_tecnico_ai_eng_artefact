"""Valores escritos à mão a partir da política (D-27)."""

import pytest

from emporio.domain.cart import CartItem, cart_totals

CG = "Campo Grande"
GD20 = CartItem(95, "Takamine GD20", 219_900, 1)
KALANI = CartItem(127, "Kalani KAL-700T", 35_900, 1, discount_percent=10)
CRAFTER = CartItem(90, "Crafter HT-100", 239_900, 1, discount_percent=18)


def item(cents: int, qty: int = 1) -> CartItem:
    return CartItem(1, "hipotético", cents, qty)


@pytest.mark.parametrize(("cents", "freight"), [(49_999, 3_500), (50_000, 0), (50_001, 0)], ids=str)
def test_p02_exact_limits_favour_customer_freight(cents: int, freight: int) -> None:
    assert cart_totals([item(cents)], CG).freight_cents == freight


@pytest.mark.parametrize(("cents", "allowed"), [(199_999, False), (200_000, True)], ids=str)
def test_p02_exact_limits_favour_customer(cents: int, allowed: bool) -> None:
    assert cart_totals([item(cents)], CG).combined_payment_allowed is allowed


def test_p03_limits_use_price_after_promotion_before_pix() -> None:
    crafter = cart_totals([CRAFTER], CG)
    assert crafter.lines[0].item.list_price_cents == 239_900
    assert crafter.subtotal_cents == 196_718
    assert crafter.combined_payment_allowed is False
    # R$ 510,00 no PIX dá 484,50, mas o frete grátis usa o valor antes do PIX.
    t = cart_totals([item(51_000)], CG)
    assert t.total_pix_cents == 48_450
    assert t.freight_rule == "gratis"


def test_p04_pix_discount_only_on_non_promotional_items() -> None:
    t = cart_totals([GD20, KALANI], CG)
    assert t.subtotal_cents == 252_210  # 2.199,00 + 323,10
    assert t.total_pix_cents == 241_215  # 2.089,05 + 323,10
    assert t.lines[1].unit_pix_cents is None


def test_p22_cart_rounds_per_unit() -> None:
    """2 x produto 124 (R$ 449,90) no PIX: 2 x 427,41 = 854,82, não 854,81."""
    t = cart_totals([CartItem(124, "produto 124", 44_990, 2)], CG)
    assert t.pix_subtotal_cents == 85_482


@pytest.mark.parametrize(
    "city", ["Campo Grande", " campo grande ", "CAMPO GRANDE", "Campo  Grande"]
)
def test_p12_metro_region_is_campo_grande(city: str) -> None:
    assert cart_totals([item(10_000)], city).freight_rule == "taxa_fixa"


@pytest.mark.parametrize("city", ["Dourados", "Três Lagoas", None])
def test_p12_other_cities_a_calcular(city: str | None) -> None:
    assert cart_totals([item(10_000)], city).freight_rule == "a_calcular"


def test_p18_no_freight_value_outside_campo_grande() -> None:
    t = cart_totals([item(45_990)], "Dourados")
    assert t.freight_cents is None
    assert t.frete_a_calcular
    assert t.total_cents == 45_990
    assert [p.n for p in t.installments] == [1, 2, 3, 4, 5]  # só os produtos


def test_p23_installments_include_freight() -> None:
    """459,90 + 35,00 = 494,90: 6x de 82,48 passa a valer (>= 80,00)."""
    t = cart_totals([item(45_990)], CG)
    assert t.total_cents == 49_490
    assert [p.n for p in t.installments] == [1, 2, 3, 4, 5, 6]
    six = t.installments[-1]
    assert (six.first_cents, six.other_cents) == (8_250, 8_248)
    assert t.total_pix_cents == 43_691 + 3_500  # PIX não desconta o frete


def test_empty_cart_rejected() -> None:
    with pytest.raises(ValueError, match="vazio"):
        cart_totals([], CG)


def test_zero_quantity_rejected() -> None:
    with pytest.raises(ValueError, match="quantidade"):
        cart_totals([item(10_000, qty=0)], CG)
