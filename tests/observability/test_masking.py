import pytest

from emporio.observability import Masker
from emporio.repositories import Customer

ANA = Customer(
    2, "Ana Carolina Ferreira", "(67) 99654-7821", "anacarol.ferreira@coldmail.com", "CG"
)


@pytest.mark.parametrize(
    "phone",
    ["(67) 99654-7821", "67 99654-7821", "+55 67 99654 7821", "67996547821", "99654-7821"],
)
def test_phone_formats(phone: str) -> None:
    assert Masker().text(f"meu número é {phone}.") == "meu número é [telefone]."


def test_email_and_cpf() -> None:
    masked = Masker().text("x.y+1@mail.com.br e cpf 123.456.789-09")
    assert masked == "[email] e cpf [cpf]"


def test_store_contacts_and_protocol_kept() -> None:
    text = "WhatsApp (67) 3321-4500, telefone (67) 3341-4444, protocolo EMP-20261127-0001"
    assert Masker().text(text) == text


def test_session_customer_name() -> None:
    masker = Masker(ANA)
    assert masker.text("Oi, Ana! Aqui é a Ana Carolina Ferreira") == "Oi, [nome]! Aqui é a [nome]"
    assert masker.text("ferreira") == "[nome]"


def test_prices_and_dates_kept() -> None:
    text = "R$ 1.234,56 em 3x, entrega até 27/11/2026, pedido 8"
    assert Masker().text(text) == text


def test_nested_values() -> None:
    masker = Masker(ANA)
    value = {"summary": "Ana ligou de 99654-7821", "items": [{"q": "a@b.com"}], "order_id": 8}
    assert masker.value(value) == {
        "summary": "[nome] ligou de [telefone]",
        "items": [{"q": "[email]"}],
        "order_id": 8,
    }
