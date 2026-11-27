"""
Situação da entrega de um pedido, calculada contra o "hoje" da loja.

`estimated_delivery` é só estimativa (princípio 2): serve para reconhecer atraso e escalar,
nunca para decidir um direito.
P-08: pedido `pending`/`confirmed` há mais de N dias úteis (P-20) está parado.
"""

from dataclasses import dataclass
from datetime import date
from typing import Literal

from emporio.domain.calendar import StoreCalendar

DeliveryState = Literal["on_time", "late", "stalled", "delivered", "cancelled"]
OPEN_STATUSES = ("pending", "confirmed")


@dataclass(frozen=True)
class DeliveryStatus:
    state: DeliveryState
    days_late: int | None = None  # dias corridos após a estimativa (`late`)
    business_days_open: int | None = None  # dias úteis desde o pedido (pending/confirmed)

    @property
    def needs_attention(self) -> bool:
        return self.state in ("late", "stalled")


def delivery_status(
    *,
    status: str,
    order_date: date,
    estimated_delivery: date | None,
    today: date,
    calendar: StoreCalendar,
    stalled_after_business_days: int,
) -> DeliveryStatus:
    if status == "delivered":
        return DeliveryStatus("delivered")
    if status == "cancelled":
        return DeliveryStatus("cancelled")
    if status in OPEN_STATUSES:
        open_days = calendar.business_days_between(order_date, today)
        state: DeliveryState = "stalled" if open_days > stalled_after_business_days else "on_time"
        return DeliveryStatus(state, business_days_open=open_days)
    if estimated_delivery is not None and today > estimated_delivery:
        return DeliveryStatus("late", days_late=(today - estimated_delivery).days)
    return DeliveryStatus("on_time")
