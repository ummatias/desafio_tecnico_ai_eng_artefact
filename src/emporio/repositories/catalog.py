"""
Catálogo de produtos

"""

import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import Engine, RowMapping, and_, case, func, select

from emporio.db.derived import cents_to_decimal, parse_money_cents
from emporio.db.schema import categories, products, promotions


@dataclass(frozen=True)
class Product:
    product_id: int
    category_id: int
    category_name: str
    name: str
    description: str | None
    price: Decimal
    stock_quantity: int
    status: str
    specs: dict[str, str]
    strings_type: str | None
    string_count: int | None
    is_electric: bool | None
    normalized_name: str
    inconsistent_listing: bool

    @property
    def available(self) -> bool:
        """À venda: ativo e com estoque. Descontinuado não é vendido nem com estoque."""
        return self.status == "active" and self.stock_quantity > 0


@dataclass(frozen=True)
class Category:
    category_id: int
    name: str
    description: str | None
    product_count: int
    available_count: int


@dataclass(frozen=True)
class Promotion:
    promotion_id: int
    product_id: int
    discount_percent: int
    description: str | None


_PRODUCT_COLUMNS = (*products.c, categories.c.name.label("category_name"))


def _product(row: RowMapping) -> Product:
    is_electric: Any = row["is_electric"]
    return Product(
        product_id=row["product_id"],
        category_id=row["category_id"],
        category_name=row["category_name"],
        name=row["name"],
        description=row["description"],
        price=cents_to_decimal(row["price_cents"]),
        stock_quantity=row["stock_quantity"],
        status=row["status"],
        specs=json.loads(row["specs_json"]),
        strings_type=row["strings_type"],
        string_count=row["string_count"],
        is_electric=None if is_electric is None else bool(is_electric),
        normalized_name=row["normalized_name"],
        inconsistent_listing=bool(row["inconsistent_listing"]),
    )


class CatalogRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def _products_query(self) -> Any:
        return select(*_PRODUCT_COLUMNS).join(
            categories, categories.c.category_id == products.c.category_id
        )

    def get_product(self, product_id: int) -> Product | None:
        query = self._products_query().where(products.c.product_id == product_id)
        with self._engine.connect() as conn:
            row = conn.execute(query).mappings().first()
        return _product(row) if row else None

    def list_products(
        self,
        *,
        category_id: int | None = None,
        min_price: Decimal | None = None,
        max_price: Decimal | None = None,
        strings_type: str | None = None,
        is_electric: bool | None = None,
        available_only: bool = True,
    ) -> list[Product]:
        conditions = []
        if category_id is not None:
            conditions.append(products.c.category_id == category_id)
        if min_price is not None:
            conditions.append(products.c.price_cents >= parse_money_cents(min_price))
        if max_price is not None:
            conditions.append(products.c.price_cents <= parse_money_cents(max_price))
        if strings_type is not None:
            conditions.append(products.c.strings_type == strings_type)
        if is_electric is not None:
            conditions.append(products.c.is_electric == is_electric)
        if available_only:
            conditions.append(products.c.status == "active")
            conditions.append(products.c.stock_quantity > 0)

        query = (
            self._products_query()
            .where(and_(True, *conditions))
            .order_by(products.c.price_cents, products.c.product_id)
        )
        with self._engine.connect() as conn:
            return [_product(row) for row in conn.execute(query).mappings()]

    def list_categories(self) -> list[Category]:
        available = and_(products.c.status == "active", products.c.stock_quantity > 0)
        query = (
            select(
                categories.c.category_id,
                categories.c.name,
                categories.c.description,
                func.count(products.c.product_id).label("product_count"),
                func.coalesce(func.sum(case((available, 1), else_=0)), 0).label("available_count"),
            )
            .select_from(categories.outerjoin(products))
            .group_by(categories.c.category_id, categories.c.name, categories.c.description)
            .order_by(categories.c.category_id)
        )
        with self._engine.connect() as conn:
            return [Category(**row) for row in conn.execute(query).mappings()]

    def active_promotions(self) -> dict[int, Promotion]:
        """Promoções ativas por produto (no máximo uma por produto, garantido pelo schema)."""
        query = select(
            promotions.c.promotion_id,
            promotions.c.product_id,
            promotions.c.discount_percent,
            promotions.c.description,
        ).where(promotions.c.is_active.is_(True))
        with self._engine.connect() as conn:
            return {row["product_id"]: Promotion(**row) for row in conn.execute(query).mappings()}

    def active_promotion(self, product_id: int) -> Promotion | None:
        """A promoção ativa do produto (o schema garante no máximo uma)."""
        query = select(
            promotions.c.promotion_id,
            promotions.c.product_id,
            promotions.c.discount_percent,
            promotions.c.description,
        ).where(promotions.c.product_id == product_id, promotions.c.is_active.is_(True))
        with self._engine.connect() as conn:
            row = conn.execute(query).mappings().first()
        return Promotion(**row) if row else None
