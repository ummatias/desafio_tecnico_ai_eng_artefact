from decimal import Decimal

import pytest

from emporio.db import derived


@pytest.mark.parametrize(
    ("raw", "cents"),
    [
        ("599.9", 59990),
        ("0.1", 10),
        ("1.15", 115),  # float: 1.15 * 100 = 114.99999999999999
        ("4.35", 435),  # float: 4.35 * 100 = 434.99999999999994
        ("2199", 219900),
        ("11499", 1149900),
        (599.9, 59990),  # float vira str antes do Decimal
    ],
)
def test_parse_money_cents_is_exact(raw: object, cents: int) -> None:
    assert derived.parse_money_cents(raw) == cents


def test_float_times_100_would_be_wrong() -> None:
    # Demontração de ADR: FLoat não é confiável para valores monetários
    assert int(1.15 * 100) == 114
    assert derived.parse_money_cents("1.15") == 115


@pytest.mark.parametrize("raw", ["-1", "12.345", "abc", "", "NaN", "Infinity"])
def test_parse_money_cents_rejects(raw: str) -> None:
    with pytest.raises(ValueError):
        derived.parse_money_cents(raw)


def test_cents_to_decimal() -> None:
    assert derived.cents_to_decimal(59990) == Decimal("599.90")
    assert str(derived.cents_to_decimal(59990)) == "599.90"


@pytest.mark.parametrize(
    "raw",
    ["(67) 99654-7821", "67996547821", "+5567996547821", "+55 (67) 99654-7821", "5567996547821"],
)
def test_normalize_phone_accepts_national_and_e164(raw: str) -> None:
    assert derived.normalize_phone(raw) == "67996547821"


def test_normalize_phone_landline() -> None:
    assert derived.normalize_phone("(67) 3321-4500") == "6733214500"


@pytest.mark.parametrize(
    "raw",
    [
        "+1 67996547821",  # DDI estrangeiro
        "99654-7821",  # sem DDD
        "0xx15 67 99654-7821",  # prefixo de operadora: não é removido
        "015 (67) 99654-7821",
        "067996547821",  # zero de discagem interurbana
        "",
    ],
)
def test_normalize_phone_rejects(raw: str) -> None:
    assert derived.normalize_phone(raw) is None


def test_normalize_name() -> None:
    assert derived.normalize_name("Takamine GD20 Dreadnought Natural") == (
        "takamine gd20 dreadnought natural"
    )
    assert derived.normalize_name("Gibson Les Paul Standard '50s") == "gibson les paul standard 50s"
    assert derived.normalize_name("  Violão  Elétrico-Aço ") == "violao eletrico aco"


SPECS_95 = {"strings": "steel", "electronics": "no"}
SPECS_101 = {"strings": "nylon", "electronics": "yes"}
SPECS_145 = {"body": "Alder", "strings": "6"}
SPECS_139 = {"shells": "Maple", "pieces": "5"}


def test_derived_takamine_gd20() -> None:
    assert derived.strings_type(SPECS_95) == "steel"
    assert derived.string_count(SPECS_95) is None
    assert derived.is_electric(SPECS_95, category_id=5) is False


def test_derived_giannini_gnf3() -> None:
    assert derived.strings_type(SPECS_101) == "nylon"
    assert derived.is_electric(SPECS_101, category_id=5) is True


def test_derived_guitar_strings_is_a_count() -> None:
    assert derived.strings_type(SPECS_145) is None
    assert derived.string_count(SPECS_145) == 6
    assert derived.is_electric(SPECS_145, category_id=1) is True


def test_derived_unknown_is_null_not_false() -> None:
    assert derived.strings_type(SPECS_139) is None
    assert derived.string_count(SPECS_139) is None
    assert derived.is_electric(SPECS_139, category_id=3) is None


@pytest.mark.parametrize(
    ("method", "expected"),
    [("credit_12x", 12), ("credit_1x", 1), ("debit", 1), ("pix", None), ("boleto", None)],
)
def test_installments(method: str, expected: int | None) -> None:
    assert derived.installments(method) == expected
