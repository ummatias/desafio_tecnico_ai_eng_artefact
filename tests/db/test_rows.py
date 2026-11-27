from datetime import date
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from emporio.db.rows import CustomerRow, OrderRow, ProductRow, PromotionRow
from emporio.db.seed import SeedError, read_csv

PRODUCT: dict[str, Any] = {
    "product_id": "81",
    "price_brl": "599.9",
    "name": "Yamaha C40 Nylon Natural",
    "category_id": "5",
    "description": "Violão clássico",
    "stock_quantity": "12",
    "status": "active",
    "specs": '{"strings":"nylon","electronics":"no"}',
    "created_at": "2021-03-15",
}

ORDER: dict[str, Any] = {
    "order_id": "8",
    "customer_id": "2",
    "order_date": "2026-02-15",
    "status": "shipped",
    "total_brl": "349.9",
    "payment_method": "debit",
    "tracking_code": "BRJL5544332BR",
    "estimated_delivery": "2026-02-28",
    "notes": "",
}


def test_valid_product() -> None:
    row = ProductRow.model_validate(PRODUCT)
    assert row.price_brl == 59990
    assert row.specs == {"strings": "nylon", "electronics": "no"}
    assert row.specs_raw == PRODUCT["specs"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("price_brl", "-10"),
        ("price_brl", "0"),
        ("price_brl", "10.999"),
        ("status", "sold_out"),
        ("stock_quantity", "-1"),
        ("specs", "{not json"),
        ("specs", "[1, 2]"),
        ("created_at", "2021-02-30"),
        ("product_id", "8.1"),
    ],
)
def test_product_rejects(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        ProductRow.model_validate({**PRODUCT, field: value})


def test_valid_order_derives_installments() -> None:
    row = OrderRow.model_validate({**ORDER, "payment_method": "credit_12x"})
    assert row.total_brl == 34990
    assert row.installments == 12
    assert row.notes is None


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"tracking_code": ""}, "exige tracking_code"),
        ({"estimated_delivery": ""}, "exige tracking_code"),
        ({"status": "delivered", "tracking_code": ""}, "exige tracking_code"),
        ({"total_brl": "0"}, "greater than 0"),
        ({"payment_method": "credit_13x"}, "forma de pagamento"),
        ({"payment_method": "cash"}, "forma de pagamento"),
        ({"status": "lost"}, "status"),
        ({"estimated_delivery": "2026-02-01"}, "anterior a order_date"),
    ],
)
def test_order_rejects(changes: dict[str, str], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        OrderRow.model_validate({**ORDER, **changes})


@pytest.mark.parametrize("status", ["pending", "confirmed", "cancelled"])
def test_order_without_shipping_fields_allowed_before_shipping(status: str) -> None:
    row = OrderRow.model_validate(
        {**ORDER, "status": status, "tracking_code": "", "estimated_delivery": ""}
    )
    assert row.tracking_code is None
    assert row.estimated_delivery is None


def test_promotion_is_active_must_be_zero_or_one() -> None:
    base = {
        "promotion_id": "1",
        "product_id": "102",
        "discount_percent": "10",
        "description": "Black Friday",
    }
    assert PromotionRow.model_validate({**base, "is_active": "1"}).is_active is True
    assert PromotionRow.model_validate({**base, "is_active": "0"}).is_active is False
    with pytest.raises(ValidationError):
        PromotionRow.model_validate({**base, "is_active": "yes"})
    with pytest.raises(ValidationError):
        PromotionRow.model_validate({**base, "is_active": "1", "discount_percent": "100"})


def test_customer_rejects_invalid_phone() -> None:
    with pytest.raises(ValidationError, match="telefone"):
        CustomerRow.model_validate(
            {"customer_id": "1", "name": "X", "phone": "123", "email": "x@x", "city": "Y"}
        )


def test_read_csv_strips_crlf_and_reports_line(tmp_path: Path) -> None:
    path = tmp_path / "customers.csv"
    path.write_bytes(
        "customer_id,name,phone,email,city\r\n"
        "1,Ana,(67) 99654-7821,a@x.com,Ponta Porã\r\n"
        "2,Bia,123,b@x.com,Ponta Porã".encode()
    )
    with pytest.raises(SeedError, match=r"customers\.csv:3: phone"):
        read_csv(path, CustomerRow)


def test_read_csv_rejects_unknown_columns(tmp_path: Path) -> None:
    path = tmp_path / "x.csv"
    path.write_text("customer_id,name,phone,email,city,extra\n1,A,67996547821,a@x,Y,z\n")
    with pytest.raises(SeedError, match="extra"):
        read_csv(path, CustomerRow)


def test_order_date_parsed() -> None:
    assert OrderRow.model_validate(ORDER).order_date == date(2026, 2, 15)
