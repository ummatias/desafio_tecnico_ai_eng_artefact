"""
Prazos e saídas escritos à mão a partir da política (D-27). 

Dias corridos, fechados no fim.
"""

from datetime import date, timedelta
from typing import Any

import pytest

from emporio.domain.exchange import ExchangeRequest, Reason, evaluate

PURCHASE = date(2026, 1, 5)
RECEIPT = date(2026, 1, 12)
NO_4_4 = {"custom_setup": False, "final_sale": False}


def req(reason: Reason, today: date, **kw: Any) -> ExchangeRequest:
    fields: dict[str, Any] = {
        "order_id": 5,
        "order_date": PURCHASE,
        "order_status": "delivered",
        "category_id": 5,
        "reason": reason,
        "today": today,
    }
    fields.update(kw)
    return ExchangeRequest(**fields)


def days(base: date, n: int) -> date:
    return base + timedelta(days=n)


# Status do pedido


@pytest.mark.parametrize(
    ("status", "code"),
    [
        ("cancelled", "order_cancelled"),
        ("pending", "order_not_delivered"),
        ("confirmed", "order_not_delivered"),
        ("shipped", "order_not_delivered"),
    ],
)
@pytest.mark.parametrize("reason", ["regret", "preference", "defect"])
def test_order_status_first(status: str, code: str, reason: Reason) -> None:
    d = evaluate(req(reason, days(PURCHASE, 3), order_status=status))
    assert (d.outcome, d.code) == ("not_applicable", code)


# Limites com rastreio


@pytest.mark.parametrize("reason", ["regret", "preference"])
def test_7_day_window_from_receipt(reason: Reason) -> None:
    inside = evaluate(req(reason, days(RECEIPT, 7), receipt_date=RECEIPT, **NO_4_4))
    outside = evaluate(req(reason, days(RECEIPT, 8), receipt_date=RECEIPT, **NO_4_4))
    assert (inside.outcome, inside.basis, inside.deadline) == (
        "eligible",
        "tracking",
        days(RECEIPT, 7),
    )
    assert outside.outcome == "expired"
    assert outside.alternatives == ("defect",)
    assert not outside.escalate


def test_defect_30_days_from_purchase() -> None:
    """§4.2: decide pela compra, sem data de recebimento."""
    d30 = evaluate(req("defect", days(PURCHASE, 30)))
    assert (d30.outcome, d30.route, d30.basis) == ("eligible", "store_exchange", "purchase")
    d31 = evaluate(req("defect", days(PURCHASE, 31), receipt_date=RECEIPT))
    assert (d31.outcome, d31.route) == ("eligible", "legal_warranty")


def test_p01_defect_within_90_days_of_receipt_escalates() -> None:
    """P-01: depois dos 30 dias, até 90 do recebimento é garantia legal, nunca "só o fabricante"."""
    d90 = evaluate(req("defect", days(RECEIPT, 90), receipt_date=RECEIPT))
    assert (d90.outcome, d90.route, d90.escalate) == ("eligible", "legal_warranty", True)
    assert "8.1" in d90.sections
    d91 = evaluate(req("defect", days(RECEIPT, 91), receipt_date=RECEIPT))
    assert (d91.outcome, d91.route, d91.escalate) == ("expired", "manufacturer_warranty", False)
    assert d91.alternatives == ("store_mediation",)


def test_p11_regret_applies_to_all_orders() -> None:
    """P-11: sem canal nos dados, todo pedido é tratado como compra online (§4.1)."""
    d = evaluate(req("regret", days(RECEIPT, 2), receipt_date=RECEIPT, **NO_4_4))
    assert (d.outcome, d.route, d.sections) == ("eligible", "return", ("4.1",))


def test_p16_preference_counts_from_receipt() -> None:
    """P-16: 7 dias do recebimento, não da compra (12 dias após a compra, 5 do recebimento)."""
    d = evaluate(req("preference", days(PURCHASE, 12), receipt_date=RECEIPT, **NO_4_4))
    assert (d.outcome, d.needs_stock) == ("eligible", True)


def test_p17_stated_date_never_decides() -> None:
    """P-17: "recebi ontem" num pedido entregue há meses não muda nada, vai para o ticket."""
    today = date(2026, 11, 27)
    yesterday = date(2026, 11, 26)
    d = evaluate(req("regret", today, receipt_date=RECEIPT, stated_receipt_date=yesterday))
    assert (d.outcome, d.stated_receipt_date) == ("expired", yesterday)
    # Sem rastreio, a data informada recente também não concede: a equipe confirma.
    d = evaluate(req("regret", today, stated_receipt_date=yesterday, **NO_4_4))
    assert (d.outcome, d.escalate, d.stated_receipt_date) == ("to_confirm", True, yesterday)


# P-24: a compra concede, nunca nega


def test_p24_purchase_date_grants_never_denies() -> None:
    d = evaluate(req("defect", days(PURCHASE, 40)))
    assert (d.outcome, d.route, d.basis) == ("eligible", "legal_warranty", "purchase")
    d = evaluate(req("regret", days(PURCHASE, 5), **NO_4_4))
    assert (d.outcome, d.basis) == ("eligible", "purchase")
    d = evaluate(req("regret", days(PURCHASE, 20), **NO_4_4))
    assert (d.outcome, d.escalate) == ("to_confirm", True)


@pytest.mark.parametrize(("reason", "limit"), [("regret", 7), ("preference", 7), ("defect", 90)])
def test_p24_purchase_boundaries(reason: Reason, limit: int) -> None:
    assert evaluate(req(reason, days(PURCHASE, limit), **NO_4_4)).outcome == "eligible"
    assert evaluate(req(reason, days(PURCHASE, limit + 1), **NO_4_4)).outcome == "to_confirm"


def test_p24_defect_100_days_without_tracking() -> None:
    """Nunca garantia do fabricante sem fonte confiável."""
    d = evaluate(req("defect", days(PURCHASE, 100)))
    assert (d.outcome, d.route, d.escalate) == ("to_confirm", None, True)


# P-25 / P-21: §4.4


def test_p25_preference_final_sale_not_eligible() -> None:
    d = evaluate(req("preference", days(RECEIPT, 3), receipt_date=RECEIPT, final_sale=True))
    assert (d.outcome, d.escalate) == ("not_eligible", False)
    assert "4.4" in d.sections


def test_p25_regret_custom_setup_escalates() -> None:
    d = evaluate(req("regret", days(RECEIPT, 3), receipt_date=RECEIPT, custom_setup=True))
    assert (d.outcome, d.escalate, d.code) == ("to_confirm", True, "section_4_4_reported")


def test_p25_defect_ignores_4_4() -> None:
    d = evaluate(req("defect", days(PURCHASE, 40), final_sale=True))
    assert (d.outcome, d.route, d.questions) == ("eligible", "legal_warranty", ())


@pytest.mark.parametrize("reason", ["regret", "preference"])
def test_p21_asks_when_window_open(reason: Reason) -> None:
    d = evaluate(req(reason, days(RECEIPT, 3), receipt_date=RECEIPT))
    assert d.outcome == "ask"
    assert d.questions == ("custom_setup", "final_sale")
    partial = evaluate(req(reason, days(RECEIPT, 3), receipt_date=RECEIPT, custom_setup=False))
    assert partial.questions == ("final_sale",)


def test_p21_no_questions_when_window_closed() -> None:
    d = evaluate(req("preference", days(RECEIPT, 8), receipt_date=RECEIPT))
    assert (d.outcome, d.questions) == ("expired", ())


def test_p21_mouthpiece_only_for_wind_categories() -> None:
    d = evaluate(req("preference", days(RECEIPT, 3), receipt_date=RECEIPT, category_id=6, **NO_4_4))
    assert d.questions == ("mouthpiece",)
    d = evaluate(
        req(
            "preference",
            days(RECEIPT, 3),
            receipt_date=RECEIPT,
            category_id=7,
            mouthpiece=True,
            **NO_4_4,
        )
    )
    assert d.outcome == "not_eligible"


# Entradas inconsistentes


def test_receipt_before_purchase_rejected() -> None:
    with pytest.raises(ValueError, match="receipt"):
        evaluate(req("defect", days(PURCHASE, 3), receipt_date=days(PURCHASE, -1)))


def test_today_before_purchase_rejected() -> None:
    with pytest.raises(ValueError, match="today"):
        evaluate(req("defect", days(PURCHASE, -1)))
