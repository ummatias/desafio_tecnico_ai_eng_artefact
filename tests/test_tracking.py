import csv
from datetime import date
from pathlib import Path

import pytest

from emporio.config import Settings
from emporio.domain.exchange import ExchangeRequest, Reason, evaluate
from emporio.tracking import (
    FixtureTrackingSource,
    NoTrackingSource,
    TrackingConfigError,
    make_tracking_source,
)
from tests.conftest import DATA_DIR, ROOT

FIXTURE = ROOT / "fixtures" / "delivery_events.csv"


@pytest.fixture(scope="module")
def source() -> FixtureTrackingSource:
    return FixtureTrackingSource(FIXTURE)


@pytest.fixture(scope="module")
def orders() -> dict[int, dict[str, str]]:
    with (DATA_DIR / "orders.csv").open(newline="", encoding="utf-8") as handle:
        return {
            int(r["order_id"]): {k: v.strip() for k, v in r.items()} for r in csv.DictReader(handle)
        }


def test_none_source_returns_nothing() -> None:
    assert NoTrackingSource().delivered_on(5, "BRTP3456789BR") is None


def test_factory_default_is_none() -> None:
    assert isinstance(make_tracking_source(Settings(_env_file=None)), NoTrackingSource)
    fixture = make_tracking_source(Settings(_env_file=None, tracking_source="fixture"))
    assert isinstance(fixture, FixtureTrackingSource)


def test_fixture_event(source: FixtureTrackingSource) -> None:
    assert source.delivered_on(5, "BRTP3456789BR") == date(2026, 1, 12)


def test_fixture_tracking_code_must_match(source: FixtureTrackingSource) -> None:
    assert source.delivered_on(5, "BRXX0000000BR") is None
    assert source.delivered_on(5, None) is None


def test_fixture_consistent_with_orders(
    source: FixtureTrackingSource, orders: dict[int, dict[str, str]]
) -> None:
    """Cada evento: pedido entregue, mesmo rastreio, entre a compra e a previsão."""
    with_event = [1, 2, 3, 4, 5]
    for order_id in with_event:
        o = orders[order_id]
        delivered = source.delivered_on(order_id, o["tracking_code"])
        assert o["status"] == "delivered"
        assert delivered is not None
        assert date.fromisoformat(o["order_date"]) <= delivered
        assert delivered <= date.fromisoformat(o["estimated_delivery"])
    for order_id in (6, 7, 8):  # 6 e 7: rastreio indisponível; 8: não entregue
        assert source.delivered_on(order_id, orders[order_id]["tracking_code"]) is None


@pytest.mark.parametrize(
    ("today", "reason", "outcome", "route"),
    [
        (date(2026, 1, 19), "regret", "eligible", "return"),
        (date(2026, 1, 20), "regret", "expired", "return"),
        (date(2026, 2, 14), "defect", "eligible", "legal_warranty"),
        (date(2026, 4, 13), "defect", "expired", "manufacturer_warranty"),
    ],
)
def test_fixture_header_scenarios(
    source: FixtureTrackingSource, today: date, reason: Reason, outcome: str, route: str
) -> None:
    """Os cenários escritos no cabeçalho do fixture, com o pedido 5."""
    decision = evaluate(
        ExchangeRequest(
            order_id=5,
            order_date=date(2026, 1, 5),
            order_status="delivered",
            category_id=5,
            reason=reason,
            today=today,
            receipt_date=source.delivered_on(5, "BRTP3456789BR"),
            custom_setup=False,
            final_sale=False,
        )
    )
    assert (decision.outcome, decision.route) == (outcome, route)


def test_invalid_fixture(tmp_path: Path) -> None:
    path = tmp_path / "ev.csv"
    path.write_text("order_id,tracking_code,delivered_on\n1,BR1BR,2026-02-31\n", encoding="utf-8")
    with pytest.raises(TrackingConfigError, match=r"ev\.csv"):
        FixtureTrackingSource(path)
