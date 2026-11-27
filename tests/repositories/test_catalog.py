from decimal import Decimal

from sqlalchemy import Engine

from emporio.repositories import CatalogRepository


def test_get_product(seeded_engine: Engine) -> None:
    product = CatalogRepository(seeded_engine).get_product(95)

    assert product is not None
    assert product.name == "Takamine GD20 Dreadnought Natural"
    assert product.price == Decimal("2199.00")
    assert product.category_name == "Violões"
    assert product.strings_type == "steel"
    assert product.is_electric is False
    assert product.inconsistent_listing is False


def test_get_unknown_product(seeded_engine: Engine) -> None:
    assert CatalogRepository(seeded_engine).get_product(1) is None


def test_default_listing_only_sells_available(seeded_engine: Engine) -> None:
    ids = {p.product_id for p in CatalogRepository(seeded_engine).list_products()}

    assert 96 not in ids  # ativo, estoque zero
    assert 113 not in ids  # descontinuado
    assert 136 not in ids  # descontinuado com 13 unidades
    assert 130 not in ids  # coming_soon
    assert 95 in ids


def test_listing_can_include_unavailable(seeded_engine: Engine) -> None:
    ids = {
        p.product_id for p in CatalogRepository(seeded_engine).list_products(available_only=False)
    }
    assert {96, 113, 130, 136} <= ids
    assert len(ids) == 65


def test_price_filter_is_inclusive(seeded_engine: Engine) -> None:
    repo = CatalogRepository(seeded_engine)

    products = repo.list_products(min_price=Decimal("599.90"), max_price=Decimal("599.90"))

    assert [p.product_id for p in products] == [81]


def test_violoes_up_to_1000(seeded_engine: Engine) -> None:
    products = CatalogRepository(seeded_engine).list_products(
        category_id=5, max_price=Decimal("1000")
    )

    assert all(p.price <= Decimal("1000") for p in products)
    assert 96 not in {p.product_id for p in products}
    assert [p.price for p in products] == sorted(p.price for p in products)


def test_filter_by_strings_and_electric(seeded_engine: Engine) -> None:
    products = CatalogRepository(seeded_engine).list_products(
        strings_type="nylon", is_electric=True
    )
    ids = {p.product_id for p in products}
    assert 101 in ids
    assert all(p.strings_type == "nylon" and p.is_electric for p in products)


def test_empty_categories_are_listed(seeded_engine: Engine) -> None:
    by_id = {c.category_id: c for c in CatalogRepository(seeded_engine).list_categories()}

    assert len(by_id) == 9
    for empty in (6, 7, 8):
        assert by_id[empty].product_count == 0
        assert by_id[empty].available_count == 0
    assert by_id[5].product_count == 35
    assert by_id[5].available_count == 33  # sem 96 (estoque 0) e 113 (descontinuado)


def test_active_promotion(seeded_engine: Engine) -> None:
    repo = CatalogRepository(seeded_engine)

    promo = repo.active_promotion(90)

    assert promo is not None
    assert promo.discount_percent == 18
    assert repo.active_promotion(93) is None  # só promoções inativas
    assert repo.active_promotion(95) is None  # nenhuma promoção
