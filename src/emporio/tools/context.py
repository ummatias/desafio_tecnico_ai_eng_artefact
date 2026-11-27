"""
O que as tools enxergam de um turno.

A identidade do cliente vem do telefone verificado pelo canal: nenhuma tool recebe `customer_id`
como argumento. `now` tem fuso e vem de `REFERENCE_DATE` ou do relógio real (`store_now`).
"""

from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Engine

from emporio.clock import store_now
from emporio.config import Settings
from emporio.domain.calendar import StoreCalendar, load_municipal_holidays
from emporio.domain.exchange import ReceiptDateSource
from emporio.repositories import (
    CatalogRepository,
    Customer,
    OrderRepository,
    TicketRepository,
)
from emporio.tools.policy_book import PolicyBook, load_policy_book
from emporio.tracking import make_tracking_source

MUNICIPAL_HOLIDAYS_FILE = "campo_grande_holidays.yaml"
POLICIES_FILE = "policies.md"


@dataclass(frozen=True)
class ToolContext:
    catalog: CatalogRepository
    orders: OrderRepository
    tickets: TicketRepository
    calendar: StoreCalendar
    tracking: ReceiptDateSource
    policies: PolicyBook
    now: datetime
    customer: Customer | None
    stalled_after_business_days: int = 5

    def __post_init__(self) -> None:
        if self.now.tzinfo is None:
            raise ValueError("now precisa de fuso")

    @property
    def today(self) -> date:
        return self.now.astimezone(self.calendar.tz).date()


def build_context(
    settings: Settings,
    engine: Engine,
    customer: Customer | None,
    *,
    now: datetime | None = None,
) -> ToolContext:
    municipal = load_municipal_holidays(settings.knowledge_dir / MUNICIPAL_HOLIDAYS_FILE)
    return ToolContext(
        catalog=CatalogRepository(engine),
        orders=OrderRepository(engine),
        tickets=TicketRepository(engine),
        calendar=StoreCalendar(municipal, ZoneInfo(settings.store_tz)),
        tracking=make_tracking_source(settings),
        policies=load_policy_book(
            settings.knowledge_dir / POLICIES_FILE, settings.assumptions_path
        ),
        now=now if now is not None else store_now(settings),
        customer=customer,
        stalled_after_business_days=settings.stalled_after_business_days,
    )
