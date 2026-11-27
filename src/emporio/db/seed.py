"""

Carga dos CSVs no banco: valida tudo antes de escrever, numa única transação.

Uso: `python -m emporio.db.seed [--force]`

"""

import argparse
import csv
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import Connection, Engine, Table, func, insert, inspect, select

from emporio.db import derived
from emporio.db.rows import (
    CategoryRow,
    CustomerRow,
    OrderItemRow,
    OrderRow,
    ProductRow,
    PromotionRow,
)
from emporio.db.schema import (
    CSV_TABLES,
    categories,
    customers,
    order_items,
    orders,
    products,
    promotions,
)

CATALOG_REVIEW_FILE = "catalog_review.yaml"


class SeedError(Exception):
    """Dados de entrada inválidos. Nada foi escrito."""


@dataclass(frozen=True)
class SeedResult:
    seeded: bool
    counts: Mapping[str, int]


class _ReviewedProduct(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int = Field(gt=0)
    motivo: str = Field(min_length=1)


class CatalogReview(BaseModel):
    """
    `knowledge/catalog_review.yaml`: produtos com cadastro inconsistente

    Revisado manualmente
    """

    model_config = ConfigDict(extra="forbid")
    revisado_em: date
    produtos: list[_ReviewedProduct]

    @property
    def product_ids(self) -> frozenset[int]:
        return frozenset(p.id for p in self.produtos)


def load_catalog_review(path: Path) -> CatalogReview:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        review = CatalogReview.model_validate(raw)
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        raise SeedError(f"{path}: {exc}") from exc
    ids = [p.id for p in review.produtos]
    duplicated = sorted({i for i in ids if ids.count(i) > 1})
    if duplicated:
        raise SeedError(f"{path}: IDs repetidos {duplicated}")
    return review


def read_csv[RowT: BaseModel](path: Path, model: type[RowT]) -> list[RowT]:
    """Lê o CSV e valida cada linha. Erros citam arquivo e linha."""
    rows: list[RowT] = []
    errors: list[str] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for record in reader:
            cleaned = {
                key.strip(): (value.strip() if isinstance(value, str) else value)
                for key, value in record.items()
            }
            try:
                rows.append(model.model_validate(cleaned))
            except ValidationError as exc:
                for err in exc.errors():
                    field = ".".join(str(part) for part in err["loc"]) or "(linha)"
                    errors.append(f"{path.name}:{reader.line_num}: {field}: {err['msg']}")
    if errors:
        raise SeedError("\n".join(errors))
    return rows


@dataclass(frozen=True)
class _Dataset:
    categories: list[CategoryRow]
    customers: list[CustomerRow]
    products: list[ProductRow]
    promotions: list[PromotionRow]
    orders: list[OrderRow]
    order_items: list[OrderItemRow]
    review: CatalogReview


def _load_dataset(data_dir: Path, knowledge_dir: Path) -> _Dataset:
    dataset = _Dataset(
        categories=read_csv(data_dir / "categories.csv", CategoryRow),
        customers=read_csv(data_dir / "customers.csv", CustomerRow),
        products=read_csv(data_dir / "products.csv", ProductRow),
        promotions=read_csv(data_dir / "promotions.csv", PromotionRow),
        orders=read_csv(data_dir / "orders.csv", OrderRow),
        order_items=read_csv(data_dir / "order_items.csv", OrderItemRow),
        review=load_catalog_review(knowledge_dir / CATALOG_REVIEW_FILE),
    )
    product_ids = {p.product_id for p in dataset.products}
    unknown = sorted(dataset.review.product_ids - product_ids)
    if unknown:
        raise SeedError(f"{CATALOG_REVIEW_FILE}: IDs que não existem em products: {unknown}")
    return dataset


def _records(dataset: _Dataset) -> dict[Table, list[dict[str, Any]]]:
    flagged = dataset.review.product_ids
    return {
        categories: [row.model_dump() for row in dataset.categories],
        customers: [
            {**row.model_dump(), "phone_digits": row.phone_digits} for row in dataset.customers
        ],
        products: [
            {
                "product_id": row.product_id,
                "category_id": row.category_id,
                "name": row.name,
                "description": row.description,
                "price_cents": row.price_brl,
                "stock_quantity": row.stock_quantity,
                "status": row.status,
                "specs_json": row.specs_raw,
                "created_at": row.created_at,
                "strings_type": derived.strings_type(row.specs),
                "string_count": derived.string_count(row.specs),
                "is_electric": derived.is_electric(row.specs, row.category_id),
                "normalized_name": derived.normalize_name(row.name),
                "cadastro_inconsistente": row.product_id in flagged,
            }
            for row in dataset.products
        ],
        promotions: [row.model_dump() for row in dataset.promotions],
        orders: [
            {
                **row.model_dump(exclude={"total_brl"}),
                "total_cents": row.total_brl,
                "installments": row.installments,
            }
            for row in dataset.orders
        ],
        order_items: [row.model_dump() for row in dataset.order_items],
    }


def _is_seeded(conn: Connection) -> bool:
    if not inspect(conn).has_table(products.name):
        return False
    return bool(conn.execute(select(func.count()).select_from(products)).scalar_one())


def _drop_csv_tables(conn: Connection) -> None:
    for table in reversed(CSV_TABLES):
        table.drop(conn, checkfirst=True)


def seed(engine: Engine, data_dir: Path, knowledge_dir: Path, *, force: bool = False) -> SeedResult:
    """Popula o banco se estiver vazio (ou recria as tabelas dos CSVs com `force`)."""
    with engine.begin() as conn:
        if not force and _is_seeded(conn):
            return SeedResult(seeded=False, counts=table_counts(conn))

    # Valida tudo antes de tocar no banco: um erro aborta a operação e nada é escrito.
    records = _records(_load_dataset(data_dir, knowledge_dir))

    with engine.begin() as conn:
        if force:
            _drop_csv_tables(conn)
        for table in CSV_TABLES:
            table.create(conn, checkfirst=True)
        for table in CSV_TABLES:
            if records[table]:
                conn.execute(insert(table), records[table])
        return SeedResult(seeded=True, counts=table_counts(conn))


def table_counts(conn: Connection) -> dict[str, int]:
    return {
        table.name: int(conn.execute(select(func.count()).select_from(table)).scalar_one())
        for table in CSV_TABLES
    }


def main(argv: list[str] | None = None) -> int:
    from emporio.config import get_settings
    from emporio.db.engine import make_engine

    parser = argparse.ArgumentParser(description="Carrega os CSVs no banco.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="recria só as tabelas dos CSVs (sessões e tickets são preservados)",
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    engine = make_engine(settings.database_url)
    try:
        result = seed(engine, settings.data_dir, settings.knowledge_dir, force=args.force)
    except SeedError as exc:
        print(f"Seed falhou; nada foi escrito.\n{exc}")
        return 1
    status = "carregado" if result.seeded else "já populado, nada a fazer"
    print(f"Banco {status}: " + ", ".join(f"{k}={v}" for k, v in result.counts.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
