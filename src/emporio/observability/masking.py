"""
Mascaramento de dados pessoais antes de gravar o trace.

Padrões genéricos (e-mail, CPF, telefone) mais os dados exatos do cliente da sessão
(nome, telefone, e-mail). Os contatos públicos da loja (P-13) não são mascarados.
"""

import re
from collections.abc import Iterable
from typing import Any

from emporio.repositories import Customer

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
CPF = re.compile(r"(?<![\w-])\d{3}\.\d{3}\.\d{3}-\d{2}(?!\d)")
PHONE = re.compile(r"(?<![\w-])(?:\+?55\s?)?(?:\(?\d{2}\)?\s?)?9?\d{4}[-\s.]?\d{4}(?!\d)")
STORE_PHONES = ("33214500", "33414444")
NAME_PARTICLES = frozenset({"da", "de", "do", "das", "dos", "e"})
MIN_NAME_PART = 3


def _phone(match: re.Match[str]) -> str:
    digits = re.sub(r"\D", "", match.group())
    return match.group() if digits.endswith(STORE_PHONES) else "[telefone]"


def _name_parts(name: str) -> list[str]:
    parts = [p for p in name.split() if p.lower() not in NAME_PARTICLES]
    return [name, *(p for p in parts if len(p) >= MIN_NAME_PART)]


class Masker:
    def __init__(self, customer: Customer | None = None, extra_names: Iterable[str] = ()) -> None:
        names = [*_name_parts(customer.name)] if customer else []
        names.extend(extra_names)
        # Mais longos primeiro: o nome completo antes das partes.
        unique = sorted({n for n in names if n}, key=len, reverse=True)
        self._names = (
            re.compile(r"\b(?:" + "|".join(re.escape(n) for n in unique) + r")\b", re.IGNORECASE)
            if unique
            else None
        )
        self._email = customer.email if customer else None

    def text(self, value: str) -> str:
        if self._email:
            value = value.replace(self._email, "[email]")
        value = EMAIL.sub("[email]", value)
        value = CPF.sub("[cpf]", value)
        value = PHONE.sub(_phone, value)
        if self._names is not None:
            value = self._names.sub("[nome]", value)
        return value

    def value(self, value: Any) -> Any:
        """Mascara strings dentro de dicts e listas (argumentos de tool)."""
        if isinstance(value, str):
            return self.text(value)
        if isinstance(value, dict):
            return {k: self.value(v) for k, v in value.items()}
        if isinstance(value, list | tuple):
            return [self.value(v) for v in value]
        return value
