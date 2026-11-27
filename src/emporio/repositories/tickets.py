"""
Tickets de atendimento humano.

O protocolo é derivado do id e da data de abertura (`EMP-AAAAMMDD-NNNN`), sem coluna própria.
"""

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import Engine, insert

from emporio.db.schema import tickets


@dataclass(frozen=True)
class Ticket:
    ticket_id: int
    customer_id: int | None
    order_id: int | None
    category: str
    priority: str
    summary: str
    stated_receipt_date: date | None
    created_at: datetime
    due_at: datetime

    @property
    def protocol(self) -> str:
        return f"EMP-{self.created_at:%Y%m%d}-{self.ticket_id:04d}"


class TicketRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def create(
        self,
        *,
        customer_id: int | None,
        order_id: int | None,
        category: str,
        priority: str,
        summary: str,
        stated_receipt_date: date | None,
        created_at: datetime,
        due_at: datetime,
    ) -> Ticket:
        if created_at.tzinfo is None or due_at.tzinfo is None:
            raise ValueError("created_at e due_at precisam de fuso")
        values = {
            "customer_id": customer_id,
            "order_id": order_id,
            "category": category,
            "priority": priority,
            "summary": summary,
            "stated_receipt_date": stated_receipt_date,
            "created_at": created_at.isoformat(),
            "due_at": due_at.isoformat(),
        }
        with self._engine.begin() as conn:
            result = conn.execute(insert(tickets).values(**values))
            (ticket_id,) = result.inserted_primary_key or (None,)
        if ticket_id is None:
            raise RuntimeError("insert sem chave primária")
        return Ticket(
            ticket_id=int(ticket_id),
            customer_id=customer_id,
            order_id=order_id,
            category=category,
            priority=priority,
            summary=summary,
            stated_receipt_date=stated_receipt_date,
            created_at=created_at,
            due_at=due_at,
        )
