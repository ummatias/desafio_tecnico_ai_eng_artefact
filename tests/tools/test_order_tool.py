"""get_order: posse, valor do pedido, estimativa e situação da entrega."""

from emporio.tools import run_tool
from tests.tools.conftest import ANA, JULIANA, RAFAEL, MakeCtx


def test_overdue_shipped_order(ctx_for: MakeCtx) -> None:
    """Pedido 8: shipped, estimativa 28/02/2026; em 27/11/2026 são 272 dias de atraso."""
    order = run_tool("get_order", {"order_id": 8}, ctx_for(ANA))["order"]
    assert (order["status"], order["delivery_state"], order["days_late"]) == (
        "shipped",
        "late",
        272,
    )
    assert order["delivery_estimate"] == "28/02/2026"
    assert (order["suggest_escalation"], order["priority"]) == (True, "high")
    assert order["tracking_code"]


def test_open_order_is_stalled(ctx_for: MakeCtx) -> None:
    order = run_tool("get_order", {"order_id": 9}, ctx_for(JULIANA))["order"]
    assert (order["status"], order["delivery_state"]) == ("confirmed", "stalled")
    assert order["business_days_open"] > 5
    assert order["suggest_escalation"] is True


def test_delivered_order(ctx_for: MakeCtx) -> None:
    result = run_tool("get_order", {"order_id": 5}, ctx_for(RAFAEL))
    order = result["order"]
    assert (order["delivery_state"], order["order_value"]) == ("delivered", "R$ 4.599,00")
    assert "suggest_escalation" not in order
    assert "você pagou" in result["note"]  # o aviso proíbe a frase


def test_other_customers_order_is_not_found(ctx_for: MakeCtx) -> None:
    result = run_tool("get_order", {"order_id": 8}, ctx_for(RAFAEL))
    assert result["error"] == "not_found"
    assert run_tool("get_order", {"order_id": 999}, ctx_for(RAFAEL))["error"] == "not_found"


def test_without_customer(ctx_for: MakeCtx) -> None:
    result = run_tool("get_order", {"order_id": 8}, ctx_for())
    assert result["error"] == "customer_not_identified"


def test_list_customer_orders(ctx_for: MakeCtx) -> None:
    result = run_tool("get_order", {}, ctx_for(ANA))
    assert [o["order_id"] for o in result["orders"]] == [8]
