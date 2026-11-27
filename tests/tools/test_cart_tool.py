"""quote_cart. Valores escritos à mão: preço x quantidade, PIX de 5% truncado, frete do §5.1."""

from emporio.tools import run_tool
from emporio.tools.cart import CART_TOTALS_KEYS
from tests.tools.conftest import GABRIEL, RAFAEL, MakeCtx

ALL_TOTALS_KEYS = {
    "lines",
    "freight",
    "freight_rule",
    "installments",
    "combined_payment_allowed",
    "subtotal",
    "pix_subtotal",
    "total",
    "total_pix",
    "freight_to_quote",
}


def test_output_covers_every_cart_totals_property() -> None:
    assert ALL_TOTALS_KEYS == CART_TOTALS_KEYS


def test_two_items_campo_grande(ctx_for: MakeCtx) -> None:
    """81 (R$ 599,90) + 120 (R$ 349,90) = R$ 949,80: frete grátis (§5.1).

    PIX: 599,90 - 29,99 = 569,91; 349,90 - 17,49 = 332,41; total R$ 902,32.
    """
    items = [{"product_id": 81}, {"product_id": 120}]
    result = run_tool("quote_cart", {"items": items}, ctx_for(RAFAEL))
    assert result.keys() >= ALL_TOTALS_KEYS
    assert result["city"] == "Campo Grande"
    assert (result["subtotal"], result["freight"], result["freight_rule"]) == (
        "R$ 949,80",
        "R$ 0,00",
        "free",
    )
    assert (result["total"], result["total_pix"]) == ("R$ 949,80", "R$ 902,32")
    assert result["combined_payment_allowed"] is False
    assert [p["n"] for p in result["installments"]] == list(range(1, 10))
    assert [line["line_pix_total"] for line in result["lines"]] == ["R$ 569,91", "R$ 332,41"]


def test_flat_freight_and_pix_never_discounts_freight(ctx_for: MakeCtx) -> None:
    """120 sozinho: R$ 349,90 + R$ 35,00. PIX: 332,41 + 35,00 = R$ 367,41."""
    result = run_tool("quote_cart", {"items": [{"product_id": 120}]}, ctx_for(RAFAEL))
    assert (result["freight"], result["freight_rule"]) == ("R$ 35,00", "flat_rate")
    assert (result["total"], result["total_pix"]) == ("R$ 384,90", "R$ 367,41")


def test_p18_quote_cart_outside_campo_grande(ctx_for: MakeCtx) -> None:
    result = run_tool("quote_cart", {"items": [{"product_id": 120}]}, ctx_for(GABRIEL))
    assert result["city"] == "Dourados"
    assert (result["freight"], result["freight_rule"], result["freight_to_quote"]) == (
        None,
        "to_quote",
        True,
    )
    assert result["total"] == "R$ 349,90"
    assert any("P-18" in n for n in result["notes"])


def test_promotional_item_has_no_pix(ctx_for: MakeCtx) -> None:
    result = run_tool("quote_cart", {"items": [{"product_id": 90}]}, ctx_for(RAFAEL))
    line = result["lines"][0]
    assert (line["unit_price"], line["unit_pix_price"], line["discount_percent"]) == (
        "R$ 1.967,18",
        None,
        18,
    )
    assert result["total_pix"] == result["total"]


def test_duplicate_lines_are_merged(ctx_for: MakeCtx) -> None:
    items = [{"product_id": 120}, {"product_id": 120, "quantity": 2}]
    result = run_tool("quote_cart", {"items": items}, ctx_for(RAFAEL))
    assert [(line["quantity"], line["line_total"]) for line in result["lines"]] == [
        (3, "R$ 1.049,70")
    ]


def test_under_review_product_accepted_with_warning(ctx_for: MakeCtx) -> None:
    """D-42: o preço do 135 é confiável; a linha leva o aviso de catálogo em revisão."""
    result = run_tool("quote_cart", {"items": [{"product_id": 135}]}, ctx_for(RAFAEL))
    line = result["lines"][0]
    assert line["catalog_under_review"] is True
    assert result["total"] == "R$ 8.732,00"


def test_unavailable_items_rejected(ctx_for: MakeCtx) -> None:
    items = [{"product_id": 96}, {"product_id": 113}, {"product_id": 9999}]
    result = run_tool("quote_cart", {"items": items}, ctx_for(RAFAEL))
    assert result["error"] == "invalid_items"
    assert result["items"] == [
        {"product_id": 96, "problem": "out_of_stock"},
        {"product_id": 113, "problem": "discontinued"},
        {"product_id": 9999, "problem": "not_found"},
    ]


def test_quantity_above_stock_does_not_reveal_stock(ctx_for: MakeCtx) -> None:
    """GD20 tem 5 unidades: pedir 6 é erro, e o número 5 não aparece na saída."""
    result = run_tool("quote_cart", {"items": [{"product_id": 95, "quantity": 6}]}, ctx_for())
    assert result["items"] == [{"product_id": 95, "problem": "insufficient_stock"}]
    text = str({k: v for k, v in result.items() if k != "items"})
    assert "5" not in text


def test_without_customer_freight_is_to_quote(ctx_for: MakeCtx) -> None:
    result = run_tool("quote_cart", {"items": [{"product_id": 120}]}, ctx_for())
    assert (result["city"], result["freight_rule"]) == (None, "to_quote")
