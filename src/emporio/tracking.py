"""
Fontes da data de recebimento.

`TRACKING_SOURCE=none` (padrão): sem rastreio, prazos contados do recebimento dão `to_confirm`.
`fixture`: lê `fixtures/delivery_events.csv`, SINTÉTICO, só para exemplos e evals.


Em produção, um adaptador da transportadora (Correios, Jadlog) entra aqui.
"""

import csv
from datetime import date
from pathlib import Path

from emporio.config import Settings
from emporio.domain.exchange import ReceiptDateSource


class TrackingConfigError(Exception):
    """Arquivo de eventos de entrega inválido."""


class NoTrackingSource:
    def delivered_on(self, order_id: int, tracking_code: str | None) -> date | None:
        return None


class FixtureTrackingSource:
    """Eventos sintéticos: o código de rastreio precisa bater com o do pedido."""

    def __init__(self, path: Path) -> None:
        self._events: dict[int, tuple[str, date]] = {}
        try:
            with path.open(newline="", encoding="utf-8") as handle:
                lines = [line for line in handle if not line.lstrip().startswith("#")]
            for row in csv.DictReader(lines):
                order_id = int(row["order_id"])
                if order_id in self._events:
                    raise ValueError(f"duplicate order {order_id}")
                self._events[order_id] = (
                    row["tracking_code"].strip(),
                    date.fromisoformat(row["delivered_on"].strip()),
                )
        except (OSError, KeyError, ValueError) as exc:
            raise TrackingConfigError(f"{path}: {exc}") from exc

    def delivered_on(self, order_id: int, tracking_code: str | None) -> date | None:
        event = self._events.get(order_id)
        if event is None or tracking_code is None or event[0] != tracking_code:
            return None
        return event[1]


def make_tracking_source(settings: Settings) -> ReceiptDateSource:
    if settings.tracking_source == "fixture":
        return FixtureTrackingSource(settings.delivery_events_path)
    return NoTrackingSource()
