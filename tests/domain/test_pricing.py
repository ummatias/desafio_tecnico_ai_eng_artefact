"""Valores escritos à mão a partir da política (D-27), nunca calculados com domain/."""

import pytest

from emporio.domain.pricing import apply_discount, pix_price, promotional_price


def test_p22_pix_truncates_discount() -> None:
    """P-22: 449,90 x 0,95 = 427,405 -> desconto truncado (22,49) -> 427,41."""
    assert pix_price(44_990, has_promotion=False) == 42_741


@pytest.mark.parametrize(
    ("product", "price", "percent", "expected"),
    [
        ("127 Kalani KAL-700T", 35_900, 10, 32_310),
        ("121 Ohana CK-20", 54_900, 20, 43_920),
        ("90 Crafter HT-100", 239_900, 18, 196_718),
        ("94 Taylor 110e", 599_900, 8, 551_908),
    ],
)
def test_p22_active_promotions_exact(product: str, price: int, percent: int, expected: int) -> None:
    assert promotional_price(price, percent) == expected, product


def test_p22_hypothetical_12_percent() -> None:
    """12% de 449,90 = 53,988 -> desconto 53,98 -> 395,92."""
    assert apply_discount(44_990, 12) == 39_592


def test_known_pix_prices() -> None:
    assert pix_price(219_900, has_promotion=False) == 208_905
    assert pix_price(104_900, has_promotion=False) == 99_655


def test_p04_no_pix_on_promotional_item() -> None:
    assert pix_price(35_900, has_promotion=True) is None


def test_no_promotion_keeps_list_price() -> None:
    assert promotional_price(35_900, None) == 35_900


@pytest.mark.parametrize("percent", [0, 100, -5])
def test_invalid_percent(percent: int) -> None:
    with pytest.raises(ValueError, match="percent"):
        apply_discount(10_000, percent)
