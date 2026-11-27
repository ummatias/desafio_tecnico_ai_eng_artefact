from collections.abc import Callable
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import Engine

from emporio.domain.calendar import StoreCalendar, load_municipal_holidays
from emporio.domain.exchange import ReceiptDateSource
from emporio.repositories import (
    CatalogRepository,
    CustomerRepository,
    OrderRepository,
    TicketRepository,
)
from emporio.tools import ToolContext
from emporio.tools.policy_book import load_policy_book
from emporio.tracking import NoTrackingSource
from tests.conftest import KNOWLEDGE_DIR, ROOT

TZ = ZoneInfo("America/Campo_Grande")
NOW = datetime(2026, 11, 27, 10, 0, tzinfo=TZ)  # sexta

# Clientes do customers.csv
RAFAEL = "(67) 98765-4321"  # 5, Campo Grande, pedido 5
ANA = "(67) 99654-7821"  # 2, Campo Grande, pedido 8 (shipped)
JULIANA = "(67) 99234-5678"  # 6, Campo Grande, pedido 9 (confirmed)
GABRIEL = "(67) 98654-3210"  # 9, Dourados, pedido 6

CALENDAR = StoreCalendar(load_municipal_holidays(KNOWLEDGE_DIR / "campo_grande_holidays.yaml"))
POLICIES = load_policy_book(KNOWLEDGE_DIR / "policies.md", ROOT / "docs" / "assumptions.md")

MakeCtx = Callable[..., ToolContext]


def make_ctx(
    engine: Engine,
    phone: str | None = None,
    *,
    now: datetime = NOW,
    tracking: ReceiptDateSource | None = None,
) -> ToolContext:
    customer = CustomerRepository(engine).get_by_phone(phone) if phone else None
    if phone:
        assert customer is not None
    return ToolContext(
        catalog=CatalogRepository(engine),
        orders=OrderRepository(engine),
        tickets=TicketRepository(engine),
        calendar=CALENDAR,
        tracking=tracking or NoTrackingSource(),
        policies=POLICIES,
        now=now,
        customer=customer,
    )


@pytest.fixture
def ctx_for(seeded_engine: Engine) -> MakeCtx:
    def factory(phone: str | None = None, **kw: object) -> ToolContext:
        return make_ctx(seeded_engine, phone, **kw)  # type: ignore[arg-type]

    return factory
