"""
Calendário da loja (§2 do manual): horário, feriados, dias úteis e horas úteis.

Puro: não lê relógio nem configuração. `now`/`start` e o fuso são sempre recebidos.
Premissas:
    - P-09 (feriados e ponto facultativo)
    - P-10 (datas especiais)
    - P-15 (horas úteis),
    - P-20 (dia útil x horas úteis) em `docs/assumptions.md`.
"""

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

import holidays
import yaml
from dateutil.easter import easter
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

DEFAULT_TZ = ZoneInfo("America/Campo_Grande")

WEEKDAY_HOURS = (time(9), time(18))
SATURDAY_HOURS = (time(9), time(13))

# P-09: único ponto facultativo com aviso. Dias relativos à Páscoa.
# Cinzas, Dia do Servidor e 31/12 (opcionais na biblioteca) são dias normais, sem aviso.
OPTIONAL_DAYS_WITH_NOTICE: tuple[tuple[str, int], ...] = (
    ("Carnaval (segunda-feira)", -48),
    ("Carnaval (terça-feira)", -47),
)

# P-10: períodos das datas especiais do §2.
CHRISTMAS_PERIOD = ((12, 1), (12, 24))
STORE_ANNIVERSARY_MONTH = 8  # §6.1: "Aniversário da Loja (Agosto)", sem dia.


class CalendarConfigError(Exception):
    """Arquivo de feriados municipais inválido."""


class _FixedHoliday(BaseModel):
    model_config = ConfigDict(extra="forbid")
    day: int = Field(alias="dia", ge=1, le=31)
    month: int = Field(alias="mes", ge=1, le=12)
    name: str = Field(alias="nome", min_length=1)

    @model_validator(mode="after")
    def _valid_date(self) -> "_FixedHoliday":
        if (self.day, self.month) == (29, 2):
            raise ValueError("feriado fixo em 29/02 não suportado")
        try:
            date(2000, self.month, self.day)  # ano bissexto: só rejeita datas impossíveis
        except ValueError:
            raise ValueError(f"data inválida: {self.day:02d}/{self.month:02d}") from None
        return self


class _MovableHoliday(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(alias="nome", min_length=1)
    days_after_easter: int = Field(alias="dias_apos_pascoa")


class MunicipalHolidays(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reviewed_at: date = Field(alias="revisado_em")
    fixed: list[_FixedHoliday] = Field(alias="fixos")
    movable: list[_MovableHoliday] = Field(alias="moveis", default=[])

    def for_year(self, year: int) -> dict[date, str]:
        days = {date(year, h.month, h.day): h.name for h in self.fixed}
        for m in self.movable:
            days[easter(year) + timedelta(days=m.days_after_easter)] = m.name
        return days


def load_municipal_holidays(path: Path) -> MunicipalHolidays:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        return MunicipalHolidays.model_validate(raw)
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        raise CalendarConfigError(f"{path}: {exc}") from exc


def black_friday(year: int) -> date:
    """P-10: sexta-feira seguinte à 4ª quinta-feira de novembro."""
    first = date(year, 11, 1)
    first_thursday = first + timedelta(days=(3 - first.weekday()) % 7)
    return first_thursday + timedelta(weeks=3, days=1)


@dataclass(frozen=True)
class Notice:
    kind: Literal["optional_day", "special_date"]
    name: str
    assumption: Literal["P-09", "P-10"]


@dataclass(frozen=True)
class StoreStatus:
    is_open: bool
    closes_at: datetime | None
    next_opening: datetime | None
    holiday_name: str | None
    notices: list[Notice] = field(default_factory=list)


class StoreCalendar:
    def __init__(self, municipal: MunicipalHolidays, tz: ZoneInfo = DEFAULT_TZ) -> None:
        self.tz = tz
        self._municipal = municipal
        self._national = holidays.country_holidays("BR", subdiv="MS")
        self._municipal_cache: dict[int, dict[date, str]] = {}

    def holiday_name(self, d: date) -> str | None:
        """Feriado nacional, de MS (biblioteca) ou de Campo Grande (YAML)."""
        if d.year not in self._municipal_cache:
            self._municipal_cache[d.year] = self._municipal.for_year(d.year)
        municipal = self._municipal_cache[d.year].get(d)
        if municipal is not None:
            return municipal
        name = self._national.get(d)
        return str(name) if name is not None else None

    def opening_hours(self, d: date) -> tuple[time, time] | None:
        """Horário do §2, ou None se a loja fecha (domingo ou feriado)."""
        if d.weekday() == 6 or self.holiday_name(d) is not None:
            return None
        return SATURDAY_HOURS if d.weekday() == 5 else WEEKDAY_HOURS

    def notices(self, d: date) -> list[Notice]:
        """Avisos do dia, abertos ou fechados (P-09, P-10)."""
        found: list[Notice] = []
        for name, offset in OPTIONAL_DAYS_WITH_NOTICE:
            if d == easter(d.year) + timedelta(days=offset):
                found.append(Notice("optional_day", name, "P-09"))
        if d == black_friday(d.year):
            found.append(Notice("special_date", "Black Friday", "P-10"))
        (start_m, start_d), (end_m, end_d) = CHRISTMAS_PERIOD
        if date(d.year, start_m, start_d) <= d <= date(d.year, end_m, end_d):
            found.append(Notice("special_date", "Natal", "P-10"))
        if d.month == STORE_ANNIVERSARY_MONTH:
            found.append(Notice("special_date", "Aniversário da Loja", "P-10"))
        return found

    def is_business_day(self, d: date) -> bool:
        """P-20: segunda a sexta, sem feriados. Sábado não é dia útil."""
        return d.weekday() < 5 and self.holiday_name(d) is None

    def add_business_days(self, start: date, n: int) -> date:
        if n < 0:
            raise ValueError("n deve ser >= 0")
        d = start
        while n > 0:
            d += timedelta(days=1)
            if self.is_business_day(d):
                n -= 1
        return d

    def business_days_between(self, start: date, end: date) -> int:
        """Dias úteis em (start, end]: o dia inicial não conta (P-20)."""
        n = 0
        d = start
        while d < end:
            d += timedelta(days=1)
            if self.is_business_day(d):
                n += 1
        return n

    def _local(self, moment: datetime) -> datetime:
        if moment.tzinfo is None:
            raise ValueError("datetime sem fuso; informe um datetime com tzinfo")
        return moment.astimezone(self.tz)

    def _windows(self, d: date) -> Iterator[tuple[datetime, datetime]]:
        while True:
            hours = self.opening_hours(d)
            if hours is not None:
                opens, closes = hours
                yield (
                    datetime.combine(d, opens, self.tz),
                    datetime.combine(d, closes, self.tz),
                )
            d += timedelta(days=1)

    def store_status(self, now: datetime) -> StoreStatus:
        local = self._local(now)
        today = local.date()
        for opens, closes in self._windows(today):
            if closes <= local:
                continue
            is_open = opens <= local
            return StoreStatus(
                is_open=is_open,
                closes_at=closes if is_open else None,
                next_opening=None if is_open else opens,
                holiday_name=self.holiday_name(today),
                notices=self.notices(today),
            )
        raise AssertionError("unreachable")

    def add_business_hours(self, start: datetime, hours: int) -> datetime:
        """
        P-15: soma horas de loja aberta (sábado incluído).

        Fora do expediente, conta a partir da próxima abertura.
        Se a contagem termina exatamente no fechamento, devolve o fechamento.
        """
        if hours < 0:
            raise ValueError("hours deve ser >= 0")
        local = self._local(start)
        remaining = timedelta(hours=hours)
        for opens, closes in self._windows(local.date()):
            if closes <= local:
                continue
            begin = max(opens, local)
            available = closes - begin
            if remaining <= available:
                return begin + remaining
            remaining -= available
        raise AssertionError("unreachable")
