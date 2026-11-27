"""Valores prontos para o cliente: o modelo copia, nunca formata nem arredonda (D-40)."""

from datetime import date, datetime
from decimal import Decimal

from emporio.db.derived import parse_money_cents


def brl(cents: int) -> str:
    """1234567 -> "R$ 12.345,67"."""
    sign = "-" if cents < 0 else ""
    reais, rest = divmod(abs(cents), 100)
    return f"{sign}R$ {reais:,}".replace(",", ".") + f",{rest:02d}"


def to_cents(value: Decimal) -> int:
    return parse_money_cents(value)


def br_date(d: date) -> str:
    return f"{d:%d/%m/%Y}"


def br_datetime(moment: datetime) -> str:
    return f"{moment:%d/%m/%Y} às {moment:%H:%M}"
