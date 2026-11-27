import pytest
from sqlalchemy import Engine

from emporio.repositories import CustomerRepository


@pytest.mark.parametrize(
    "phone",
    ["(67) 99654-7821", "67996547821", "+5567996547821", "+55 (67) 99654-7821"],
)
def test_get_by_phone_any_format(seeded_engine: Engine, phone: str) -> None:
    customer = CustomerRepository(seeded_engine).get_by_phone(phone)

    assert customer is not None
    assert customer.customer_id == 2
    assert customer.name == "Ana Carolina Ferreira"


@pytest.mark.parametrize(
    "phone",
    [
        "+1 67996547821",  # DDI estrangeiro
        "99654-7821",  # sem DDD
        "0xx15 67 99654-7821",  # prefixo de operadora não é removido
        "015 (67) 99654-7821",
        "(67) 90000-0000",  # válido, mas não é cliente
    ],
)
def test_get_by_phone_returns_none(seeded_engine: Engine, phone: str) -> None:
    assert CustomerRepository(seeded_engine).get_by_phone(phone) is None


def test_shared_email_customers_are_distinct(seeded_engine: Engine) -> None:
    repo = CustomerRepository(seeded_engine)
    a = repo.get_by_phone("(67) 98543-2109")
    b = repo.get_by_phone("(67) 99456-3456")
    assert a is not None and b is not None
    assert a.email == b.email == "bruno.martins@jmail.com"
    assert {a.customer_id, b.customer_id} == {11, 43}
