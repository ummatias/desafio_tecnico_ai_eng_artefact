"""
Parcelamento no cartão de crédito em centavos inteiros.

P-05: parcelas iguais truncadas ao centavo, resto na primeira, o mínimo vale para a menor.
P-06: até 3x, mínimo de R$ 50,00 (exceto 1x). 
P-07: vale o §3.1, não a tabela do §3.
"""

from dataclasses import dataclass

MAX_INSTALLMENTS = 12


def min_installment_cents(n: int) -> int:
    """Parcela mínima do §3.1 para `n` parcelas (P-06, P-07)."""
    if n == 1:
        return 0
    if n <= 3:
        return 5_000
    if n <= 6:
        return 8_000
    return 10_000


@dataclass(frozen=True)
class InstallmentPlan:
    n: int
    first_cents: int
    other_cents: int
    total_cents: int


def split(total_cents: int, n: int) -> InstallmentPlan:
    """P-05: R$ 459,90 em 12x = 1 x R$ 38,38 + 11 x R$ 38,32."""
    if total_cents < 0:
        raise ValueError("total_cents deve ser >= 0")
    if not 1 <= n <= MAX_INSTALLMENTS:
        raise ValueError(f"n deve estar entre 1 e {MAX_INSTALLMENTS}")
    other = total_cents // n
    first = total_cents - other * (n - 1)
    return InstallmentPlan(n=n, first_cents=first, other_cents=other, total_cents=total_cents)


def installment_plans(total_cents: int) -> list[InstallmentPlan]:
    """Planos válidos de 1x a 12x, sem juros. O mínimo é verificado na menor parcela."""
    plans = (split(total_cents, n) for n in range(1, MAX_INSTALLMENTS + 1))
    return [p for p in plans if p.other_cents >= min_installment_cents(p.n)]
