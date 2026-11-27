"""check_exchange: posse, item do pedido e data de recebimento só da fonte confiável."""

from datetime import datetime

from emporio.tools import run_tool
from emporio.tracking import FixtureTrackingSource
from tests.conftest import ROOT
from tests.tools.conftest import ANA, RAFAEL, TZ, MakeCtx

FIXTURE = FixtureTrackingSource(ROOT / "fixtures" / "delivery_events.csv")
NO_4_4 = {"custom_setup": False, "final_sale": False}


def on(y: int, m: int, d: int) -> datetime:
    return datetime(y, m, d, 10, 0, tzinfo=TZ)


def regret(ctx_for: MakeCtx, when: datetime, **kw: object) -> dict[str, object]:
    args = {"order_id": 5, "product_id": 97, "reason": "regret", **NO_4_4, **kw}
    return run_tool("check_exchange", args, ctx_for(RAFAEL, now=when, tracking=FIXTURE))


def test_regret_day_7_with_tracking(ctx_for: MakeCtx) -> None:
    """Pedido 5: entregue em 12/01/2026 (fixture); 19/01 é o 7º dia."""
    result = regret(ctx_for, on(2026, 1, 19))
    assert (result["outcome"], result["route"], result["basis"]) == (
        "eligible",
        "return",
        "tracking",
    )
    assert (result["receipt_date"], result["deadline"]) == ("12/01/2026", "19/01/2026")


def test_regret_day_8_with_tracking(ctx_for: MakeCtx) -> None:
    result = regret(ctx_for, on(2026, 1, 20))
    assert (result["outcome"], result["escalate"], result["alternatives"]) == (
        "expired",
        False,
        ["defect"],
    )


def test_without_tracking_stated_date_goes_to_ticket_only(ctx_for: MakeCtx) -> None:
    args = {
        "order_id": 5,
        "product_id": 97,
        "reason": "regret",
        "stated_receipt_date": "2026-11-26",
        **NO_4_4,
    }
    result = run_tool("check_exchange", args, ctx_for(RAFAEL))
    assert (result["outcome"], result["escalate"], result["receipt_date"]) == (
        "to_confirm",
        True,
        None,
    )
    assert result["stated_receipt_date"] == "26/11/2026"


def test_preference_reports_replacement_availability(ctx_for: MakeCtx) -> None:
    result = regret(ctx_for, on(2026, 1, 15), reason="preference", replacement_product_id=96)
    assert (result["outcome"], result["needs_stock"]) == ("eligible", True)
    assert result["replacement"] == {
        "product_id": 96,
        "name": "Giannini GF-3D Dreadnought Sunburst",
        "availability": "out_of_stock",
    }


def test_asks_section_4_4(ctx_for: MakeCtx) -> None:
    args = {"order_id": 5, "product_id": 97, "reason": "preference"}
    result = run_tool(
        "check_exchange", args, ctx_for(RAFAEL, now=on(2026, 1, 15), tracking=FIXTURE)
    )
    assert (result["outcome"], result["questions"]) == ("ask", ["custom_setup", "final_sale"])


def test_product_must_be_in_the_order(ctx_for: MakeCtx) -> None:
    result = regret(ctx_for, on(2026, 1, 19), product_id=95)
    assert result["error"] == "product_not_in_order"


def test_other_customers_order(ctx_for: MakeCtx) -> None:
    args = {"order_id": 5, "product_id": 97, "reason": "defect"}
    assert run_tool("check_exchange", args, ctx_for(ANA))["error"] == "not_found"


def test_reference_date_before_purchase(ctx_for: MakeCtx) -> None:
    assert regret(ctx_for, on(2025, 12, 1))["error"] == "invalid_request"


def test_not_delivered_order(ctx_for: MakeCtx) -> None:
    args = {"order_id": 8, "product_id": 120, "reason": "defect"}
    result = run_tool("check_exchange", args, ctx_for(ANA))
    assert (result["outcome"], result["code"]) == ("not_applicable", "order_not_delivered")
