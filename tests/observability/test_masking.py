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


@pytest.mark.parametrize(
    "phone", ["(67) 3321-4500", "+55 67 3321-4500", "3321-4500", "(67) 3341-4444", "33414444"]
)
def test_store_phones_kept(phone: str) -> None:
    """P-13: só as formas exatas dos números da loja passam."""
    assert Masker().text(f"fale no {phone}") == f"fale no {phone}"


@pytest.mark.parametrize("phone", ["99 3321-4500", "(11) 3321-4500", "(11) 3341-4444"])
def test_same_ending_other_number_masked(phone: str) -> None:
    assert Masker().text(f"meu número é {phone}") == "meu número é [telefone]"


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


NB_HYPHEN = chr(0x2011)


@pytest.mark.parametrize("dash", ["-", NB_HYPHEN, chr(0x2010), chr(0x2013), chr(0x2212)])
def test_protocol_is_never_a_phone(dash: str) -> None:
    protocol = f"EMP{dash}20261127{dash}0001"
    assert Masker().text(f"Seu protocolo é **{protocol}**.") == f"Seu protocolo é **{protocol}**."


def test_unicode_hyphen_phone_is_masked() -> None:
    text = f"me liga no (67) 99654{NB_HYPHEN}7821 ou no 98765{chr(0x2013)}4321"
    assert Masker().text(text) == "me liga no [telefone] ou no [telefone]"


def test_unicode_hyphen_cpf_is_masked() -> None:
    assert Masker().text(f"cpf 123.456.789{NB_HYPHEN}09") == "cpf [cpf]"


def test_phone_next_to_protocol_still_masked() -> None:
    text = f"EMP{NB_HYPHEN}20261127{NB_HYPHEN}0001, fone 99654{NB_HYPHEN}7821"
    assert Masker().text(text) == f"EMP{NB_HYPHEN}20261127{NB_HYPHEN}0001, fone [telefone]"


def test_store_phone_with_unicode_hyphen_kept() -> None:
    text = f"WhatsApp (67) 3321{NB_HYPHEN}4500"
    assert Masker().text(text) == text
