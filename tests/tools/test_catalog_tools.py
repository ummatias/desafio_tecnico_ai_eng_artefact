"""search_products e get_product. Valores escritos à mão a partir do CSV e da política."""

from emporio.tools import run_tool
from tests.tools.conftest import MakeCtx


def ids(items: list[dict[str, object]]) -> list[object]:
    return [i["product_id"] for i in items]


# search_products


def test_fuzzy_name_finds_gd20(ctx_for: MakeCtx) -> None:
    result = run_tool("search_products", {"query": "takamine gd 20"}, ctx_for())
    assert ids(result["products"])[0] == 95


def test_category_word_in_query(ctx_for: MakeCtx) -> None:
    """O nome do produto não traz a categoria: "ukulele kala ka-c" acha o Kala KA-C (120)."""
    result = run_tool("search_products", {"query": "ukulele kala ka-c"}, ctx_for())
    assert ids(result["products"])[0] == 120


def test_category_word_alone_lists_the_category(ctx_for: MakeCtx) -> None:
    result = run_tool("search_products", {"query": "ukulele", "limit": 20}, ctx_for())
    found = ids(result["products"])
    assert 118 in found and 120 in found  # Kalani KAL-300S, Kala KA-C
    assert {p["category"] for p in result["products"]} == {"Ukuleles"}


def test_singular_of_plural_category(ctx_for: MakeCtx) -> None:
    result = run_tool("search_products", {"query": "violão yamaha f310"}, ctx_for())
    assert "F310" in result["products"][0]["name"]


def test_ambiguous_category_words_are_not_filters(ctx_for: MakeCtx) -> None:
    """ "cordas de guitarra" é acessório: "cordas" não lista a categoria Cordas Orquestrais."""
    result = run_tool("search_products", {"query": "cordas", "limit": 20}, ctx_for())
    assert "Cordas Orquestrais" not in {p["category"] for p in result["products"]}


def test_violoes_up_to_1000(ctx_for: MakeCtx) -> None:
    result = run_tool(
        "search_products", {"category": "violões", "max_price": 1000, "limit": 20}, ctx_for()
    )
    found = ids(result["products"])
    assert 96 not in found  # sem estoque
    assert 113 not in found  # descontinuado
    assert 112 in found  # R$ 999,00: o limite é inclusivo
    assert 101 not in found  # R$ 1.049,00
    # Giannini GNF-3 CEQ: R$ 1.049,00, R$ 996,55 no PIX
    assert [(p["product_id"], p["pix_price"]) for p in result["within_budget_with_pix"]] == [
        (101, "R$ 996,55")
    ]
    assert all(p["availability"] == "available" for p in result["products"])


def test_inconsistent_listing_goes_to_under_review(ctx_for: MakeCtx) -> None:
    """Princípio 3: "jazz bass" só aparece na descrição do 135; nem "temos" nem "não temos"."""
    result = run_tool("search_products", {"query": "jazz bass"}, ctx_for())
    assert result["products"] == []
    assert ids(result["under_review"]) == [135]


def test_inconsistent_listing_never_in_main_list(ctx_for: MakeCtx) -> None:
    result = run_tool("search_products", {"category": "baixos"}, ctx_for())
    assert not set(ids(result["products"])) & set(range(135, 145))
    assert set(ids(result["under_review"])) <= set(range(135, 145))


def test_unavailable_items_with_reason(ctx_for: MakeCtx) -> None:
    ctx = ctx_for()
    for query, product_id, reason in [
        ("giannini gf-3d", 96, "out_of_stock"),
        ("shelby sn-7c", 113, "discontinued"),
        ("kala ka-abp-ctg", 130, "coming_soon"),
    ]:
        result = run_tool("search_products", {"query": query}, ctx)
        assert product_id not in ids(result["products"])
        unavailable = {p["product_id"]: p["availability"] for p in result["unavailable"]}
        assert unavailable[product_id] == reason


def test_empty_category(ctx_for: MakeCtx) -> None:
    result = run_tool("search_products", {"category": "sopro"}, ctx_for())
    assert result["products"] == []
    assert any(n.startswith("empty_category") for n in result["notes"])


def test_unknown_category_lists_valid_ones(ctx_for: MakeCtx) -> None:
    result = run_tool("search_products", {"category": "amplificadores"}, ctx_for())
    assert result["error"] == "unknown_category"
    assert "5 Violões" in result["categories"]


def test_active_promotion_in_search(ctx_for: MakeCtx) -> None:
    """Promoção 19: Crafter HT-100 (90) com 18%: 2.399,00 - 431,82 = 1.967,18, sem PIX."""
    result = run_tool("search_products", {"query": "crafter ht-100"}, ctx_for())
    p = result["products"][0]
    assert (p["product_id"], p["price"], p["list_price"], p["pix_price"]) == (
        90,
        "R$ 1.967,18",
        "R$ 2.399,00",
        None,
    )


# get_product


def test_gd20_inactive_promotion(ctx_for: MakeCtx) -> None:
    """Promoção 4 (12%) do GD20 está inativa: preço de tabela e PIX de 5%."""
    result = run_tool("get_product", {"product_id": 95}, ctx_for())
    assert result["promotion"] is None
    assert (result["price"], result["pix_price"]) == ("R$ 2.199,00", "R$ 2.089,05")


def test_promotion_shows_original_price_and_percent(ctx_for: MakeCtx) -> None:
    result = run_tool("get_product", {"product_id": 90}, ctx_for())
    assert result["promotion"] == {
        "description": "Desconto Exclusivo",
        "discount_percent": 18,
        "original_price": "R$ 2.399,00",
        "promotional_price": "R$ 1.967,18",
    }
    assert result["pix_price"] is None


def test_installments_only_valid_plans(ctx_for: MakeCtx) -> None:
    """R$ 349,90 (120): 4x de R$ 87,47 >= 80 vale; 5x de R$ 69,98 < 80 não (§3.1)."""
    plans = run_tool("get_product", {"product_id": 120}, ctx_for())["installments"]
    assert [p["n"] for p in plans] == [1, 2, 3, 4]
    assert plans[2] == {"n": 3, "first": "R$ 116,64", "other": "R$ 116,63", "total": "R$ 349,90"}


def test_p19_no_campaign_discount_without_active_promotion(ctx_for: MakeCtx) -> None:
    """Black Friday (27/11/2026): a promoção 1 do produto 102 está inativa, preço cheio."""
    result = run_tool("get_product", {"product_id": 102}, ctx_for())
    assert result["promotion"] is None
    assert result["price"] == "R$ 3.899,00"


def test_inconsistent_listing_hides_specs(ctx_for: MakeCtx) -> None:
    result = run_tool("get_product", {"product_id": 135}, ctx_for())
    assert result["catalog_under_review"] is True
    assert "specs" not in result
    assert "description" not in result
    assert result["price"] == "R$ 8.732,00"


def test_product_not_found(ctx_for: MakeCtx) -> None:
    assert run_tool("get_product", {"product_id": 9999}, ctx_for())["error"] == "not_found"
