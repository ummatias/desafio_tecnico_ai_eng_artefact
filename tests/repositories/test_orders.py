from datetime import date
from decimal import Decimal

from sqlalchemy import Engine

from emporio.repositories import OrderRepository


def test_customer_sees_own_order(seeded_engine: Engine) -> None:
    order = OrderRepository(seeded_engine).get_for_customer(8, customer_id=2)

    assert order is not None
    assert order.status == "shipped"
    assert order.tracking_code == "BRJL5544332BR"
    assert order.estimated_delivery == date(2026, 2, 28)
    assert order.total == Decimal("349.90")
    assert [i.product_id for i in order.items] == [120]


def test_other_customers_order_is_invisible(seeded_engine: Engine) -> None:
    assert OrderRepository(seeded_engine).get_for_customer(1, customer_id=2) is None


def test_order_with_two_items(seeded_engine: Engine) -> None:
    order = OrderRepository(seeded_engine).get_for_customer(15, customer_id=18)

    assert order is not None
    assert [(i.product_id, i.quantity) for i in order.items] == [(82, 1), (106, 1)]
    assert order.installments == 12


def test_items_carry_current_product_status(seeded_engine: Engine) -> None:
    order = OrderRepository(seeded_engine).get_for_customer(3, customer_id=12)

    assert order is not None
    assert order.items[0].product_status == "coming_soon"
    assert order.items[0].quantity == 2


def test_list_for_customer_newest_first(seeded_engine: Engine) -> None:
    orders = OrderRepository(seeded_engine).list_for_customer(3)

    assert [o.order_id for o in orders] == [19, 1]


def test_list_for_customer_without_orders(seeded_engine: Engine) -> None:
    assert OrderRepository(seeded_engine).list_for_customer(50) == []
