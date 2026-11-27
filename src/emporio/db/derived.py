"""Funções puras que derivam colunas a partir dos dados do CSV."""

import re
import unicodedata
from decimal import Decimal, InvalidOperation
from typing import Literal

StringsType = Literal["nylon", "steel"]

GUITARRAS_CATEGORY_ID = 1
_CREDIT_RE = re.compile(r"credit_(\d{1,2})x")
_NON_DIGIT_RE = re.compile(r"\D")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def parse_money_cents(raw: object) -> int:
    """Converte um valor em reais para centavos sem passar por float."""
    text = str(raw).strip()
    try:
        value = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"valor monetário inválido: {text!r}") from exc
    if not value.is_finite():
        raise ValueError(f"valor monetário inválido: {text!r}")
    if value < 0:
        raise ValueError(f"valor monetário negativo: {text!r}")
    exponent = value.as_tuple().exponent
    if isinstance(exponent, int) and exponent < -2:
        raise ValueError(f"valor monetário com mais de 2 casas decimais: {text!r}")
    return int(value * 100)


def cents_to_decimal(cents: int) -> Decimal:
    return (Decimal(cents) / 100).quantize(Decimal("0.01"))


def normalize_phone(raw: str) -> str | None:
    """
        Normaliza um número de telefone brasileiro.

        Telefone brasileiro -> dígitos nacionais (DDD + número, 10 ou 11 dígitos).

        Aceita formatado ("(67) 99654-7821") e E.164 ("+5567996547821"): remove o DDI 55.
        Prefixo de operadora, DDI estrangeiro ou número sem DDD -> None.
    """
    digits = _NON_DIGIT_RE.sub("", raw)
    if len(digits) in (12, 13) and digits.startswith("55"):
        digits = digits[2:]
    if len(digits) not in (10, 11) or digits[0] == "0":
        return None
    return digits


def normalize_name(name: str) -> str:
    """Minúsculas, sem acentos, pontuação vira espaço, espaços colapsados."""
    decomposed = unicodedata.normalize("NFKD", name)
    ascii_only = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return _NON_ALNUM_RE.sub(" ", ascii_only.lower()).strip()


def strings_type(specs: dict[str, str]) -> StringsType | None:
    """`specs.strings` quando é material (nylon/aço)"""
    value = specs.get("strings", "").strip().lower()
    if value == "nylon":
        return "nylon"
    if value == "steel":
        return "steel"
    return None


def string_count(specs: dict[str, str]) -> int | None:
    value = specs.get("strings", "").strip()
    return int(value) if value.isdigit() else None


def is_electric(specs: dict[str, str], category_id: int) -> bool | None:
    """
        `specs.electronics` quando existe
        Guitarras são elétricas, senão desconhecido (None).
    """
    electronics = specs.get("electronics", "").strip().lower()
    if electronics == "yes":
        return True
    if electronics == "no":
        return False
    if category_id == GUITARRAS_CATEGORY_ID:
        return True
    return None


def installments(payment_method: str) -> int | None:
    """
        Número de parcelas: 
            credit_<n>x -> n
            débito -> 1
            PIX e boleto -> None
    """
    if payment_method == "debit":
        return 1
    match = _CREDIT_RE.fullmatch(payment_method)
    if match:
        return int(match.group(1))
    return None
