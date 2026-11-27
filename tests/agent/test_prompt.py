import re
from datetime import datetime

from sqlalchemy import Engine

from emporio.agent import PROMPT_VERSION, build_system_prompt
from emporio.agent.prompt import AGENDA_DAYS
from tests.tools.conftest import ANA, TZ, make_ctx

THURSDAY = datetime(2026, 11, 26, 10, 0, tzinfo=TZ)


def _prompt(engine: Engine, phone: str | None = ANA, now: datetime = THURSDAY) -> str:
    return build_system_prompt(make_ctx(engine, phone, now=now))


def test_p13_contacts(seeded_engine: Engine) -> None:
    """P-13: WhatsApp do §7, telefone do §1.2 nunca chamado de WhatsApp, e-mail sem acento."""
    prompt = _prompt(seeded_engine)
    assert "WhatsApp: (67) 3321-4500" in prompt
    assert "(67) 3341-4444" in prompt
    assert "contato@emporiodamusica.com.br" in prompt
    assert "empóriodamusica" not in prompt
    for line in prompt.splitlines():
        if "3341-4444" in line:
            assert line.startswith("- Telefone: (67) 3341-4444")
            assert "nunca o chame de WhatsApp" in line


def test_p14_no_partner_store(seeded_engine: Engine) -> None:
    """P-14: só instrumentos; acessórios redirecionados sem nomear loja parceira."""
    prompt = _prompt(seeded_engine)
    assert "exclusivamente com instrumentos musicais" in prompt
    assert "Não indique nenhuma loja parceira específica" in prompt
    assert re.search(r"loja parceira [A-Z]", prompt) is None


def test_p10_thursday_agenda(seeded_engine: Engine) -> None:
    """P-10: na quinta 26/11, amanhã (Black Friday) tem horário normal e aviso."""
    prompt = _prompt(seeded_engine)
    assert (
        "- amanhã (sexta-feira, 27/11/2026): aberta das 09:00 às 18:00 · data especial: "
        "Black Friday" in prompt
    )
    assert "redes sociais e no WhatsApp" in prompt
    agenda = [line for line in prompt.splitlines() if re.match(r"- .*\d{2}/\d{2}/\d{4}\)?:", line)]
    assert len(agenda) == AGENDA_DAYS


def test_now_and_open_status(seeded_engine: Engine) -> None:
    prompt = _prompt(seeded_engine)
    assert "Data e hora: quinta-feira, 26/11/2026, 10:00" in prompt
    assert "Loja agora: aberta, fecha às 18:00." in prompt


def test_closed_on_sunday_shows_next_opening(seeded_engine: Engine) -> None:
    prompt = _prompt(seeded_engine, now=datetime(2026, 11, 29, 15, 0, tzinfo=TZ))
    assert "Loja agora: fechada; reabre amanhã (segunda-feira, 30/11/2026) às 09:00." in prompt


def test_holiday_named(seeded_engine: Engine) -> None:
    """25/12 é feriado: a loja fecha e o nome aparece na agenda e no estado."""
    prompt = _prompt(seeded_engine, now=datetime(2026, 12, 25, 10, 0, tzinfo=TZ))
    assert "- hoje (sexta-feira, 25/12/2026): fechada (feriado:" in prompt
    assert "Loja agora: fechada (" in prompt
    assert "reabre amanhã (sábado, 26/12/2026) às 09:00." in prompt


def test_customer_first_name_only(seeded_engine: Engine) -> None:
    prompt = _prompt(seeded_engine)
    assert "Primeiro nome: Ana." in prompt
    assert "Ana Carolina Ferreira" not in prompt
    assert "99654-7821" not in prompt
    assert "anacarol" not in prompt


def test_unidentified_customer(seeded_engine: Engine) -> None:
    prompt = _prompt(seeded_engine, phone=None)
    assert "Não identificado pelo telefone" in prompt
    assert "Primeiro nome" not in prompt


def test_fully_rendered(seeded_engine: Engine) -> None:
    prompt = _prompt(seeded_engine)
    assert PROMPT_VERSION == "v1"
    assert re.search(r"\$\w", prompt) is None
    assert "untrusted_data" in prompt
    assert "quote_cart" in prompt
