"""
Mascaramento de dados pessoais antes de gravar o trace.

Padrões genéricos (e-mail, CPF, telefone) mais os dados exatos do cliente da sessão
(nome, telefone, e-mail). Só as formas exatas dos números públicos da loja (P-13) ficam;
um número com o mesmo final, mas outro DDD ou prefixo, é mascarado.
"""

import re
from collections.abc import Iterable
from typing import Any

from emporio.repositories import Customer

# Hífens que o modelo usa no lugar do "-" (U+2010 a U+2015, U+2212): também são separadores.
UNICODE_DASHES = "".join(chr(c) for c in (*range(0x2010, 0x2016), 0x2212))
_DASH = re.escape("-" + UNICODE_DASHES)

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
CPF = re.compile(rf"(?<![\w{_DASH}])\d{{3}}\.\d{{3}}\.\d{{3}}[{_DASH}]\d{{2}}(?!\d)")
PHONE = re.compile(
    rf"(?<![\w{_DASH}])(?:\+?55\s?)?(?:\(?\d{{2}}\)?\s?)?9?\d{{4}}[{_DASH}\s.]?\d{{4}}(?!\d)"
)
# Protocolo de chamado (EMP-AAAAMMDD-NNNN): nunca é telefone, com qualquer hífen.
PROTOCOL = re.compile(rf"EMP[{_DASH}]\d{{8}}[{_DASH}]\d{{4}}")
# Dígitos das formas aceitas: com 55 e DDD, só com DDD e só o número.
STORE_PHONES = frozenset(
    f"{prefix}{number}" for number in ("33214500", "33414444") for prefix in ("5567", "67", "")
)
NAME_PARTICLES = frozenset({"da", "de", "do", "das", "dos", "e"})
MIN_NAME_PART = 3


def _phone(match: re.Match[str]) -> str:
    digits = re.sub(r"\D", "", match.group())
    return match.group() if digits in STORE_PHONES else "[telefone]"


def _numbers(value: str) -> str:
    return PHONE.sub(_phone, CPF.sub("[cpf]", value))


def _outside_protocols(value: str) -> str:
    """Mascara CPF e telefone só fora dos protocolos, que ficam intactos."""
    parts: list[str] = []
    last = 0
    for match in PROTOCOL.finditer(value):
        parts.extend((_numbers(value[last : match.start()]), match.group()))
        last = match.end()
    parts.append(_numbers(value[last:]))
    return "".join(parts)


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
        value = _outside_protocols(value)
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
