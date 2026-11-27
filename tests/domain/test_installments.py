"""Valores escritos à mão a partir da política (D-27)."""

import pytest

from emporio.domain.installments import installment_plans, split


def ns(total: int) -> list[int]:
    return [p.n for p in installment_plans(total)]


def test_p05_truncate_remainder_on_first() -> None:
    """P-05: R$ 459,90 em 12x = 1 x 38,38 + 11 x 38,32."""
    plan = split(45_990, 12)
    assert (plan.first_cents, plan.other_cents) == (3_838, 3_832)
    assert plan.first_cents + 11 * plan.other_cents == 45_990


def test_459_90_valid_up_to_5x() -> None:
    assert ns(45_990) == [1, 2, 3, 4, 5]
    five = split(45_990, 5)
    assert (five.first_cents, five.other_cents) == (9_198, 9_198)


def test_gd20_12x() -> None:
    plans = installment_plans(219_900)
    assert plans[-1].n == 12
    assert (plans[-1].first_cents, plans[-1].other_cents) == (18_325, 18_325)


def test_p06_minimum_50_up_to_3x() -> None:
    """P-06: 1x sem mínimo, 2x e 3x com parcela mínima de R$ 50,00."""
    assert ns(3_000) == [1]
    assert ns(9_998) == [1]  # 2x de 49,99
    assert ns(10_000) == [1, 2]  # 2x de 50,00


def test_p07_section_3_1_overrides_payment_table() -> None:
    """P-07: 4x de R$ 80,00 vale (§3.1), embora a tabela do §3 diga mínimo de R$ 100,00."""
    assert 4 in ns(32_000)
    assert 5 not in ns(32_000)


@pytest.mark.parametrize("n", [0, 13])
def test_invalid_n(n: int) -> None:
    with pytest.raises(ValueError, match="n deve"):
        split(10_000, n)
