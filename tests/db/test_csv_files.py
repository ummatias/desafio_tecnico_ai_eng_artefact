from datetime import date
from pathlib import Path

import pytest
from pydantic import BaseModel

from emporio.db.rows import (
    CategoryRow,
    CustomerRow,
    OrderItemRow,
    OrderRow,
    ProductRow,
    PromotionRow,
)
from emporio.db.seed import read_csv
from tests.conftest import DATA_DIR


@pytest.mark.parametrize(
    "name", ["categories", "customers", "order_items", "orders", "products", "promotions"]
)
def test_files_are_crlf_without_final_newline(name: str) -> None:
    raw = (DATA_DIR / f"{name}.csv").read_bytes()
    assert b"\r\n" in raw
    assert not raw.endswith(b"\n")


def _rows[T: BaseModel](name: str, model: type[T]) -> list[T]:
    return read_csv(Path(DATA_DIR / f"{name}.csv"), model)


def test_categories_last_column() -> None:
    rows = _rows("categories", CategoryRow)
    assert rows[0].description == "Guitarras elétricas de todos os estilos, do rock ao jazz"
    assert rows[-1].description == "Ukuleles soprano, concert, tenor e barítono"


def test_customers_last_column() -> None:
    rows = _rows("customers", CustomerRow)
    by_id = {r.customer_id: r for r in rows}
    assert by_id[17].city == "Ponta Porã"  # linha do meio, CRLF
    assert rows[-1].city == "Ponta Porã"  # última linha, sem newline
    assert {r.city for r in rows} == {
        "Campo Grande",
        "Corumbá",
        "Dourados",
        "Ponta Porã",
        "Três Lagoas",
    }


def test_order_items_last_column() -> None:
    rows = _rows("order_items", OrderItemRow)
    assert (rows[0].order_id, rows[0].product_id) == (1, 93)
    assert (rows[-1].order_id, rows[-1].product_id) == (20, 84)


def test_orders_last_column() -> None:
    rows = _rows("orders", OrderRow)
    by_id = {r.order_id: r for r in rows}
    assert by_id[1].notes is None
    assert by_id[17].notes == "Pedido cancelado pelo cliente antes do processamento"
    assert rows[-1].notes == "Endereço de entrega inválido informado pelo cliente"


def test_products_last_column() -> None:
    rows = _rows("products", ProductRow)
    assert rows[0].created_at == date(2021, 3, 15)
    assert rows[-1].created_at == date(2020, 4, 22)


def test_promotions_last_column() -> None:
    rows = _rows("promotions", PromotionRow)
    active = {r.promotion_id for r in rows if r.is_active}
    assert active == {12, 14, 19, 24}
    assert rows[-1].is_active is False
