from datetime import date

import pytest
from sqlalchemy import Engine

from emporio.domain.calendar import StoreCalendar, load_municipal_holidays
from emporio.domain.orders import delivery_status
from emporio.repositories import OrderRepository
from tests.conftest import KNOWLEDGE_DIR

CAL = StoreCalendar(load_municipal_holidays(KNOWLEDGE_DIR / "campo_grande_holidays.yaml"))


def status(st: str, ordered: date, today: date, estimate: date | None = None) -> str:
    return delivery_status(
        status=st,
        order_date=ordered,
        estimated_delivery=estimate,
        today=today,
        calendar=CAL,
        stalled_after_business_days=5,
    ).state


@pytest.mark.parametrize("st", ["pending", "confirmed"])
def test_p08_stalled_after_5_business_days(st: str) -> None:
    """Pedido na segunda 09/11/2026: 5 dias úteis em 16/11 (em dia), 6 em 17/11 (parado)."""
    assert status(st, date(2026, 11, 9), date(2026, 11, 16)) == "on_time"
    assert status(st, date(2026, 11, 9), date(2026, 11, 17)) == "stalled"


def test_p08_holiday_does_not_count() -> None:
    """20/11/2026 (Consciência Negra): pedido em 16/11, 5 dias úteis só em 24/11."""
    assert status("pending", date(2026, 11, 16), date(2026, 11, 23)) == "on_time"
    assert status("pending", date(2026, 11, 16), date(2026, 11, 24)) == "on_time"
    assert status("pending", date(2026, 11, 16), date(2026, 11, 25)) == "stalled"


def test_p08_open_orders_stalled(seeded_engine: Engine) -> None:
    """Os pedidos 9-16 estão abertos desde fev-mar de 2026 (A01)."""
    repo = OrderRepository(seeded_engine)
    orders = [o for c in range(1, 51) for o in repo.list_for_customer(c)]
    open_ids = sorted(
        o.order_id
        for o in orders
        if status(o.status, o.order_date, date(2026, 11, 27), o.estimated_delivery) == "stalled"
    )
    assert open_ids == list(range(9, 17))


def test_shipped_late_counts_calendar_days() -> None:
    result = delivery_status(
        status="shipped",
        order_date=date(2026, 2, 15),
        estimated_delivery=date(2026, 2, 28),
        today=date(2026, 3, 2),
        calendar=CAL,
        stalled_after_business_days=5,
    )
    assert (result.state, result.days_late, result.needs_attention) == ("late", 2, True)
    assert status("shipped", date(2026, 2, 15), date(2026, 2, 28), date(2026, 2, 28)) == "on_time"


@pytest.mark.parametrize(("st", "state"), [("delivered", "delivered"), ("cancelled", "cancelled")])
def test_closed_orders(st: str, state: str) -> None:
    assert status(st, date(2026, 1, 5), date(2026, 11, 27)) == state


def test_business_days_between() -> None:
    assert CAL.business_days_between(date(2026, 11, 27), date(2026, 11, 30)) == 1  # sex -> seg
    assert CAL.business_days_between(date(2026, 11, 19), date(2026, 11, 23)) == 1  # pula 20/11
    assert CAL.business_days_between(date(2026, 11, 27), date(2026, 11, 27)) == 0
