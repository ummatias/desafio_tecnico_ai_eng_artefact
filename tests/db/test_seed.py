import shutil
from pathlib import Path

import pytest
import yaml
from sqlalchemy import Engine, Table, func, insert, select, text
from sqlalchemy.exc import IntegrityError

from emporio.db.schema import CSV_TABLES, orders, products, promotions, tickets
from emporio.db.seed import CATALOG_REVIEW_FILE, SeedError, load_catalog_review, seed
from tests.conftest import DATA_DIR, KNOWLEDGE_DIR

EXPECTED_COUNTS = {
    "categories": 9,
    "customers": 50,
    "products": 65,
    "promotions": 25,
    "orders": 20,
    "order_items": 22,
}


def test_seed_loads_every_row(empty_engine: Engine) -> None:
    result = seed(empty_engine, DATA_DIR, KNOWLEDGE_DIR)

    assert result.seeded is True
    assert dict(result.counts) == EXPECTED_COUNTS
    with empty_engine.connect() as conn:
        ids = conn.execute(select(products.c.product_id)).scalars().all()
    assert sorted(ids) == list(range(81, 146))


def test_second_seed_is_a_no_op(empty_engine: Engine) -> None:
    seed(empty_engine, DATA_DIR, KNOWLEDGE_DIR)

    result = seed(empty_engine, DATA_DIR, KNOWLEDGE_DIR)

    assert result.seeded is False
    assert dict(result.counts) == EXPECTED_COUNTS


def test_inconsistent_flag_matches_catalog_review(seeded_engine: Engine) -> None:
    review_ids = load_catalog_review(KNOWLEDGE_DIR / CATALOG_REVIEW_FILE).product_ids

    with seeded_engine.connect() as conn:
        flagged = set(
            conn.execute(
                select(products.c.product_id).where(products.c.inconsistent_listing.is_(True))
            ).scalars()
        )

    assert flagged == review_ids


def test_seed_keeps_original_specs_text(seeded_engine: Engine) -> None:
    with seeded_engine.connect() as conn:
        specs = conn.execute(
            select(products.c.specs_json).where(products.c.product_id == 135)
        ).scalar_one()
    assert specs == '{"body": "Ash", "neck": "Maple", "strings": "4", "color": "Red"}'


def test_order_columns(seeded_engine: Engine) -> None:
    with seeded_engine.connect() as conn:
        row = conn.execute(select(orders).where(orders.c.order_id == 2)).mappings().one()
    assert row["total_cents"] == 599900
    assert row["installments"] == 6


def _knowledge_with(tmp_path: Path, product_ids: list[int]) -> Path:
    knowledge = tmp_path / "knowledge"
    knowledge.mkdir()
    content = {
        "revisado_em": "2026-11-27",
        "produtos": [{"id": i, "motivo": "teste"} for i in product_ids],
    }
    (knowledge / CATALOG_REVIEW_FILE).write_text(yaml.safe_dump(content), encoding="utf-8")
    return knowledge


def _table_exists(engine: Engine, name: str) -> bool:
    with engine.connect() as conn:
        query = text("SELECT count(*) FROM sqlite_master WHERE type='table' AND name=:n")
        return bool(conn.execute(query, {"n": name}).scalar_one())


def test_unknown_review_id_fails_and_writes_nothing(empty_engine: Engine, tmp_path: Path) -> None:
    knowledge = _knowledge_with(tmp_path, [135, 999])

    with pytest.raises(SeedError, match=r"\[999\]"):
        seed(empty_engine, DATA_DIR, knowledge)

    assert not _table_exists(empty_engine, "products")


def test_invalid_csv_row_fails_and_writes_nothing(empty_engine: Engine, tmp_path: Path) -> None:
    data = tmp_path / "data"
    shutil.copytree(DATA_DIR, data)
    orders_csv = data / "orders.csv"
    orders_csv.write_bytes(orders_csv.read_bytes().replace(b",shipped,", b",lost,"))

    with pytest.raises(SeedError, match=r"orders\.csv:9: status"):
        seed(empty_engine, data, KNOWLEDGE_DIR)

    assert not _table_exists(empty_engine, "categories")


def test_force_recreates_only_csv_tables(empty_engine: Engine) -> None:
    seed(empty_engine, DATA_DIR, KNOWLEDGE_DIR)
    ticket = {
        "customer_id": 2,
        "category": "other",
        "priority": "normal",
        "summary": "teste",
        "created_at": "2026-11-27T10:00:00-04:00",
        "due_at": "2026-11-30T16:00:00-04:00",
    }
    with empty_engine.begin() as conn:
        conn.execute(insert(tickets), [ticket, ticket])
        conn.execute(products.update().values(stock_quantity=0))

    result = seed(empty_engine, DATA_DIR, KNOWLEDGE_DIR, force=True)

    assert result.seeded is True
    assert dict(result.counts) == EXPECTED_COUNTS
    with empty_engine.connect() as conn:
        assert conn.execute(select(func.count()).select_from(tickets)).scalar_one() == 2
        stock = conn.execute(
            select(products.c.stock_quantity).where(products.c.product_id == 95)
        ).scalar_one()
    assert stock == 5


def test_csv_tables_order() -> None:
    assert [t.name for t in CSV_TABLES] == list(EXPECTED_COUNTS)


def test_second_active_promotion_for_same_product_is_rejected(empty_engine: Engine) -> None:
    seed(empty_engine, DATA_DIR, KNOWLEDGE_DIR)
    with pytest.raises(IntegrityError), empty_engine.begin() as conn:
        conn.execute(
            insert(promotions).values(
                promotion_id=99, product_id=90, discount_percent=5, is_active=True
            )
        )


def test_inactive_duplicate_promotion_is_allowed(empty_engine: Engine) -> None:
    seed(empty_engine, DATA_DIR, KNOWLEDGE_DIR)
    with empty_engine.begin() as conn:
        conn.execute(
            insert(promotions).values(
                promotion_id=99, product_id=90, discount_percent=5, is_active=False
            )
        )


def test_foreign_keys_are_enforced(empty_engine: Engine) -> None:
    seed(empty_engine, DATA_DIR, KNOWLEDGE_DIR)
    with pytest.raises(IntegrityError), empty_engine.begin() as conn:
        conn.execute(
            insert(promotions).values(
                promotion_id=99, product_id=12345, discount_percent=5, is_active=False
            )
        )


@pytest.mark.parametrize(
    "values",
    [
        {"status": "shipped", "tracking_code": None, "estimated_delivery": None},
        {"total_cents": 0},
        {"payment_method": "credit_13x"},
        {"installments": 13},
    ],
)
def test_orders_check_constraints(empty_engine: Engine, values: dict[str, object]) -> None:
    seed(empty_engine, DATA_DIR, KNOWLEDGE_DIR)
    with pytest.raises(IntegrityError), empty_engine.begin() as conn:
        conn.execute(orders.update().where(orders.c.order_id == 8).values(**values))


def test_cancelled_order_without_tracking_is_valid(empty_engine: Engine) -> None:
    seed(empty_engine, DATA_DIR, KNOWLEDGE_DIR)
    with empty_engine.begin() as conn:
        conn.execute(
            orders.update()
            .where(orders.c.order_id == 8)
            .values(status="cancelled", tracking_code=None, estimated_delivery=None)
        )


def test_failed_force_rolls_back_the_drop(
    empty_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DROP e INSERT na mesma transação: falha no meio não deixa o banco vazio."""
    import emporio.db.seed as seed_module

    seed(empty_engine, DATA_DIR, KNOWLEDGE_DIR)
    real_records = seed_module._records

    def records_with_conflict(dataset: object) -> dict[Table, list[dict[str, object]]]:
        records = real_records(dataset)
        duplicate = {**records[promotions][18], "promotion_id": 999}  # 2ª promo ativa do 90
        records[promotions] = [*records[promotions], duplicate]
        return records

    monkeypatch.setattr(seed_module, "_records", records_with_conflict)

    with pytest.raises(IntegrityError):
        seed(empty_engine, DATA_DIR, KNOWLEDGE_DIR, force=True)

    with empty_engine.connect() as conn:
        assert conn.execute(select(func.count()).select_from(products)).scalar_one() == 65
