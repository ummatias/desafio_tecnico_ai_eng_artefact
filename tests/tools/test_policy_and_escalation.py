from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import Engine, func, select

from emporio.db.schema import tickets
from emporio.db.seed import seed
from emporio.tools import run_tool
from emporio.tools.policy_book import PolicyConfigError, load_policy_book
from tests.conftest import DATA_DIR, KNOWLEDGE_DIR
from tests.tools.conftest import ANA, RAFAEL, TZ, MakeCtx, make_ctx

# get_policy


def test_section_1_2_includes_p13(ctx_for: MakeCtx) -> None:
    result = run_tool("get_policy", {"section_id": "1.2"}, ctx_for())
    assert result["title"] == "Dados da Empresa"
    assert "(67) 3341-4444" in result["text"]
    [p13] = result["assumptions"]
    assert p13["id"] == "P-13"
    assert "(67) 3321-4500" in p13["premise"]


def test_section_text_and_annotations(ctx_for: MakeCtx) -> None:
    result = run_tool("get_policy", {"section_id": "§4.1"}, ctx_for())
    assert result["section_id"] == "4.1"
    assert result["text"].startswith("- O cliente pode solicitar a devolução em até 7")
    assert not any(line.startswith(">") for line in result["text"].splitlines())
    assert result["annotations"][0].startswith("**Marco:** 7 dias corridos")
    assert [a["id"] for a in result["assumptions"]] == ["P-17", "P-20", "P-11", "P-24", "P-25"]


def test_unknown_section(ctx_for: MakeCtx) -> None:
    result = run_tool("get_policy", {"section_id": "11"}, ctx_for())
    assert result["error"] == "unknown_section"
    assert result["sections"]["8.1"] == "Garantia Legal"


def test_missing_assumption_fails_on_load(tmp_path: Path) -> None:
    policies = tmp_path / "p.md"
    policies.write_text("## 1 Título\n\n> texto\n\n**Premissas:** P-99.\n", encoding="utf-8")
    assumptions = tmp_path / "a.md"
    assumptions.write_text("# Premissas\n", encoding="utf-8")
    with pytest.raises(PolicyConfigError, match="P-99"):
        load_policy_book(policies, assumptions)


# escalate_to_human


@pytest.fixture
def fresh_engine(empty_engine: Engine) -> Engine:
    seed(empty_engine, DATA_DIR, KNOWLEDGE_DIR)
    return empty_engine


def test_ticket_with_protocol_and_return_deadline(fresh_engine: Engine) -> None:
    """Sexta 27/11 17h + 24 horas úteis = quarta 02/12 10h (P-15)."""
    ctx = make_ctx(fresh_engine, ANA, now=datetime(2026, 11, 27, 17, 0, tzinfo=TZ))
    args = {"summary": "Pedido 8 atrasado", "category": "order_delay", "priority": "high"}
    first = run_tool("escalate_to_human", {**args, "order_id": 8}, ctx)
    second = run_tool("escalate_to_human", args, ctx)
    assert (first["protocol"], first["return_by"]) == ("EMP-20261127-0001", "02/12/2026 às 10:00")
    assert second["protocol"] == "EMP-20261127-0002"
    with fresh_engine.connect() as conn:
        row = conn.execute(select(tickets).where(tickets.c.ticket_id == 1)).mappings().one()
    assert (row["customer_id"], row["order_id"], row["priority"]) == (2, 8, "high")
    assert row["due_at"] == "2026-12-02T10:00:00-04:00"


def test_stated_receipt_date_goes_to_ticket(fresh_engine: Engine) -> None:
    ctx = make_ctx(fresh_engine, RAFAEL)
    args = {
        "summary": "Arrependimento, cliente diz que recebeu ontem",
        "category": "exchange",
        "order_id": 5,
        "stated_receipt_date": "2026-11-26",
    }
    assert "protocol" in run_tool("escalate_to_human", args, ctx)
    with fresh_engine.connect() as conn:
        stated = conn.execute(select(tickets.c.stated_receipt_date)).scalar_one()
    assert str(stated) == "2026-11-26"


def test_escalation_checks_order_ownership(fresh_engine: Engine) -> None:
    ctx = make_ctx(fresh_engine, RAFAEL)
    args = {"summary": "x", "category": "order_delay", "order_id": 8}
    assert run_tool("escalate_to_human", args, ctx)["error"] == "not_found"
    with fresh_engine.connect() as conn:
        assert conn.execute(select(func.count()).select_from(tickets)).scalar_one() == 0


def test_escalation_without_customer(fresh_engine: Engine) -> None:
    ctx = make_ctx(fresh_engine)
    exchange = {"summary": "x", "category": "exchange"}
    assert run_tool("escalate_to_human", exchange, ctx)["error"] == "customer_not_identified"
    other = run_tool("escalate_to_human", {"summary": "dúvida", "category": "other"}, ctx)
    assert other["protocol"] == "EMP-20261127-0001"
