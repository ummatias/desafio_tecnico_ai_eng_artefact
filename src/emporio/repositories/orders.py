"""
Pedidos

A leitura de pedidos é feita pelo cliente (customer_id) e não pelo vendedor,
para não expor pedidos de outros clientes.

"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import Connection, Engine, RowMapping, select

from emporio.db.derived import cents_to_decimal
from emporio.db.schema import order_items, orders, products


@dataclass(frozen=True)
class OrderItem:
    product_id: int
    name: str
    quantity: int
    product_status: str


@dataclass(frozen=True)
class Order:
    order_id: int
    customer_id: int
    order_date: date
    status: str
    total: Decimal
    payment_method: str
    installments: int | None
    tracking_code: str | None
    estimated_delivery: date | None
    notes: str | None
    items: tuple[OrderItem, ...]


class OrderRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def list_for_customer(self, customer_id: int) -> list[Order]:
        query = (
            select(orders)
            .where(orders.c.customer_id == customer_id)
            .order_by(orders.c.order_date.desc(), orders.c.order_id.desc())
        )
        with self._engine.connect() as conn:
            return [self._order(conn, row) for row in conn.execute(query).mappings()]

    def get_for_customer(self, order_id: int, customer_id: int) -> Order | None:
        """Pedido de outro cliente devolve None"""
        query = select(orders).where(
            orders.c.order_id == order_id, orders.c.customer_id == customer_id
        )
        with self._engine.connect() as conn:
            row = conn.execute(query).mappings().first()
            return self._order(conn, row) if row else None

    def _order(self, conn: Connection, row: RowMapping) -> Order:
        items_query = (
            select(
                order_items.c.product_id,
                products.c.name,
                order_items.c.quantity,
                products.c.status.label("product_status"),
            )
            .join(products, products.c.product_id == order_items.c.product_id)
            .where(order_items.c.order_id == row["order_id"])
            .order_by(order_items.c.product_id)
        )
        items = tuple(OrderItem(**item) for item in conn.execute(items_query).mappings())
        return Order(
            order_id=row["order_id"],
            customer_id=row["customer_id"],
            order_date=row["order_date"],
            status=row["status"],
            total=cents_to_decimal(row["total_cents"]),
            payment_method=row["payment_method"],
            installments=row["installments"],
            tracking_code=row["tracking_code"],
            estimated_delivery=row["estimated_delivery"],
            notes=row["notes"],
            items=items,
        )
