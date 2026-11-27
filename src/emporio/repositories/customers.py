"""
Clientes

Utilizando telefone como identificador, pois email não é unico

Caso:
    Cliente     Nome                    Telefone            Email
    11          Bruno Carvalho Martins  (67) 98543-2109     bruno.martins@jmail.com
    43          Bruno Martins           (67) 99456-3456     bruno.martins@jmail.com
"""

from dataclasses import dataclass

from sqlalchemy import Engine, select

from emporio.db.derived import normalize_phone
from emporio.db.schema import customers


@dataclass(frozen=True)
class Customer:
    customer_id: int
    name: str
    phone: str
    email: str
    city: str


class CustomerRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def get_by_phone(self, phone: str) -> Customer | None:
        digits = normalize_phone(phone)
        if digits is None:
            return None
        query = select(
            customers.c.customer_id,
            customers.c.name,
            customers.c.phone,
            customers.c.email,
            customers.c.city,
        ).where(customers.c.phone_digits == digits)
        with self._engine.connect() as conn:
            row = conn.execute(query).mappings().first()
        return Customer(**row) if row else None
