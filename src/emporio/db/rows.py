"""Modelos pydantic que validam cada linha dos CSVs antes de qualquer escrita no banco.

As regras espelham os CHECKs do schema

Caso hajá uma violação, a mesma será reportada com arquivo e linha do CSV
em vez de um erro genérico do SQLite.
"""

import json
import re
from datetime import date
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator, model_validator

from emporio.db import derived

ProductStatus = Literal["active", "discontinued", "coming_soon"]
OrderStatus = Literal["pending", "confirmed", "shipped", "delivered", "cancelled"]

PAYMENT_METHODS: tuple[str, ...] = (
    "pix",
    "boleto",
    "debit",
    *(f"credit_{n}x" for n in range(1, 13)),
)
# Status em que o pedido ainda não saiu: rastreio e previsão podem faltar.
STATUSES_WITHOUT_SHIPPING: tuple[str, ...] = ("pending", "confirmed", "cancelled")

_STRICT_INT_RE = re.compile(r"\d+")


def _money(value: Any) -> int:
    return derived.parse_money_cents(value)


def _strict_int(value: Any) -> Any:
    if isinstance(value, str):
        if not _STRICT_INT_RE.fullmatch(value):
            raise ValueError(f"inteiro inválido: {value!r}")
        return int(value)
    return value


def _empty_to_none(value: Any) -> Any:
    return None if value == "" else value


Cents = Annotated[int, BeforeValidator(_money)]
Id = Annotated[int, BeforeValidator(_strict_int), Field(gt=0)]
NonNegativeInt = Annotated[int, BeforeValidator(_strict_int), Field(ge=0)]
Text = Annotated[str, Field(min_length=1)]
OptionalText = Annotated[str | None, BeforeValidator(_empty_to_none)]
OptionalDate = Annotated[date | None, BeforeValidator(_empty_to_none)]


class _Row(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class CategoryRow(_Row):
    category_id: Id
    name: Text
    description: OptionalText


class CustomerRow(_Row):
    customer_id: Id
    name: Text
    phone: Text
    email: Text
    city: Text

    @field_validator("phone")
    @classmethod
    def _phone_is_valid(cls, value: str) -> str:
        if derived.normalize_phone(value) is None:
            raise ValueError(f"telefone inválido: {value!r}")
        return value

    @property
    def phone_digits(self) -> str:
        digits = derived.normalize_phone(self.phone)
        assert digits is not None  # garantido pelo validador
        return digits


class ProductRow(_Row):
    product_id: Id
    price_brl: Cents = Field(gt=0)
    name: Text
    category_id: Id
    description: OptionalText
    stock_quantity: NonNegativeInt
    status: ProductStatus
    specs: dict[str, str]
    specs_raw: str
    created_at: date

    @model_validator(mode="before")
    @classmethod
    def _keep_raw_specs(cls, data: Any) -> Any:
        if isinstance(data, dict) and isinstance(data.get("specs"), str):
            return {**data, "specs_raw": data["specs"]}
        return data

    @field_validator("specs", mode="before")
    @classmethod
    def _parse_specs(cls, value: Any) -> Any:
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError as exc:
                raise ValueError(f"specs não é JSON válido: {exc}") from exc
            if not isinstance(parsed, dict):
                raise ValueError("specs deve ser um objeto JSON")
            return parsed
        return value


class PromotionRow(_Row):
    promotion_id: Id
    product_id: Id
    discount_percent: Annotated[int, BeforeValidator(_strict_int), Field(ge=1, le=99)]
    description: OptionalText
    is_active: bool

    @field_validator("is_active", mode="before")
    @classmethod
    def _zero_or_one(cls, value: Any) -> Any:
        if isinstance(value, str):
            if value not in ("0", "1"):
                raise ValueError(f"is_active deve ser 0 ou 1: {value!r}")
            return value == "1"
        return value


class OrderRow(_Row):
    order_id: Id
    customer_id: Id
    order_date: date
    status: OrderStatus
    total_brl: Cents = Field(gt=0)
    payment_method: str
    tracking_code: OptionalText
    estimated_delivery: OptionalDate
    notes: OptionalText

    @field_validator("payment_method")
    @classmethod
    def _known_payment_method(cls, value: str) -> str:
        if value not in PAYMENT_METHODS:
            raise ValueError(f"forma de pagamento desconhecida: {value!r}")
        return value

    @model_validator(mode="after")
    def _shipping_fields(self) -> Self:
        if self.status not in STATUSES_WITHOUT_SHIPPING and (
            self.tracking_code is None or self.estimated_delivery is None
        ):
            raise ValueError(
                f"pedido {self.status} exige tracking_code e estimated_delivery preenchidos"
            )
        if self.estimated_delivery is not None and self.estimated_delivery < self.order_date:
            raise ValueError("estimated_delivery anterior a order_date")
        return self

    @property
    def installments(self) -> int | None:
        return derived.installments(self.payment_method)


class OrderItemRow(_Row):
    order_id: Id
    quantity: Annotated[int, BeforeValidator(_strict_int), Field(gt=0)]
    product_id: Id
