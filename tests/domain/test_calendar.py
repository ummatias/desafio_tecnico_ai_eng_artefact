from datetime import UTC, date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from emporio.domain.calendar import (
    CalendarConfigError,
    StoreCalendar,
    black_friday,
    load_municipal_holidays,
)
from tests.conftest import KNOWLEDGE_DIR

TZ = ZoneInfo("America/Campo_Grande")
WEEKDAY = (time(9), time(18))


def at(y: int, m: int, d: int, hh: int = 0, mm: int = 0) -> datetime:
    return datetime(y, m, d, hh, mm, tzinfo=TZ)


@pytest.fixture(scope="module")
def cal() -> StoreCalendar:
    return StoreCalendar(load_municipal_holidays(KNOWLEDGE_DIR / "campo_grande_holidays.yaml"))


def test_weekday_open_until_18(cal: StoreCalendar) -> None:
    status = cal.store_status(at(2026, 11, 25, 10))  # quarta
    assert status.is_open
    assert status.closes_at == at(2026, 11, 25, 18)
    assert status.next_opening is None


@pytest.mark.parametrize(("hh", "mm", "is_open"), [(12, 59, True), (13, 0, False), (13, 1, False)])
def test_saturday_closes_at_13(cal: StoreCalendar, hh: int, mm: int, is_open: bool) -> None:
    status = cal.store_status(at(2026, 11, 28, hh, mm))
    assert status.is_open is is_open
    if not is_open:
        assert status.next_opening == at(2026, 11, 30, 9)  # segunda


def test_sunday_closed(cal: StoreCalendar) -> None:
    assert cal.opening_hours(date(2026, 11, 29)) is None
    assert cal.store_status(at(2026, 11, 29, 10)).next_opening == at(2026, 11, 30, 9)


def test_national_holiday_closed_with_name(cal: StoreCalendar) -> None:
    status = cal.store_status(at(2026, 11, 2, 10))  # Finados, segunda
    assert not status.is_open
    assert status.holiday_name == "Finados"
    assert status.next_opening == at(2026, 11, 3, 9)


def test_ms_holiday_closed_with_name(cal: StoreCalendar) -> None:
    """11/10/2027 é segunda. Em 2026 cai num domingo e não testaria o feriado."""
    d = date(2027, 10, 11)
    assert d.weekday() == 0
    assert cal.opening_hours(d) is None
    assert cal.holiday_name(d) == "Criação do Estado"


def test_naive_datetime_rejected(cal: StoreCalendar) -> None:
    with pytest.raises(ValueError, match="fuso"):
        cal.store_status(datetime(2026, 11, 25, 10))


def test_utc_now_converted_to_store_tz(cal: StoreCalendar) -> None:
    # 21:30 UTC = 17:30 em Campo Grande (UTC-4): ainda aberta.
    status = cal.store_status(datetime(2026, 11, 25, 21, 30, tzinfo=UTC))
    assert status.is_open
    assert status.closes_at == at(2026, 11, 25, 18)


# P-09: feriados municipais e ponto facultativo


@pytest.mark.parametrize(
    ("d", "name"),
    [
        (date(2026, 6, 13), "Santo Antônio (padroeiro)"),
        (date(2026, 8, 26), "Aniversário de Campo Grande"),
        (date(2026, 6, 4), "Corpus Christi"),
    ],
)
def test_p09_campo_grande_holidays_closed(cal: StoreCalendar, d: date, name: str) -> None:
    assert cal.opening_hours(d) is None
    assert cal.holiday_name(d) == name


def test_p09_corpus_christi_is_movable(cal: StoreCalendar) -> None:
    assert cal.holiday_name(date(2027, 5, 27)) == "Corpus Christi"


def test_p09_dec_8_open(cal: StoreCalendar) -> None:
    assert cal.opening_hours(date(2026, 12, 8)) == WEEKDAY


@pytest.mark.parametrize("d", [date(2026, 2, 16), date(2026, 2, 17)])
def test_p09_carnaval_regular_hours_with_notice(cal: StoreCalendar, d: date) -> None:
    assert cal.opening_hours(d) == WEEKDAY
    assert [(n.kind, n.premissa) for n in cal.notices(d)] == [("ponto_facultativo", "P-09")]


def test_p09_ash_wednesday_no_notice(cal: StoreCalendar) -> None:
    assert cal.opening_hours(date(2026, 2, 18)) == WEEKDAY
    assert cal.notices(date(2026, 2, 18)) == []


@pytest.mark.parametrize("d", [date(2026, 12, 31), date(2026, 10, 28)])
def test_p09_other_optional_days_no_notice(cal: StoreCalendar, d: date) -> None:
    assert cal.opening_hours(d) == WEEKDAY
    assert cal.notices(d) == []


def test_p09_yaml_unknown_key_fails(tmp_path: Path) -> None:
    path = tmp_path / "h.yaml"
    path.write_text("revisado_em: 2026-11-27\nfixos: []\nextra: 1\n", encoding="utf-8")
    with pytest.raises(CalendarConfigError, match=r"h\.yaml"):
        load_municipal_holidays(path)


def _write_fixed(tmp_path: Path, dia: int, mes: int) -> Path:
    path = tmp_path / "h.yaml"
    path.write_text(
        f"revisado_em: 2026-11-27\nfixos:\n  - {{dia: {dia}, mes: {mes}, nome: X}}\n",
        encoding="utf-8",
    )
    return path


def test_p09_yaml_impossible_date_fails(tmp_path: Path) -> None:
    path = _write_fixed(tmp_path, 31, 2)
    with pytest.raises(CalendarConfigError, match=r"h\.yaml(.|\n)*data inválida: 31/02"):
        load_municipal_holidays(path)


def test_p09_yaml_feb_29_rejected(tmp_path: Path) -> None:
    path = _write_fixed(tmp_path, 29, 2)
    with pytest.raises(CalendarConfigError, match="29/02 não suportado"):
        load_municipal_holidays(path)


# P-10: datas especiais


def test_p10_black_friday_regular_hours(cal: StoreCalendar) -> None:
    """Perguntado na quinta 26/11: amanhã (Black Friday) abre no horário normal, com aviso."""
    d = date(2026, 11, 27)
    assert black_friday(2026) == d
    assert cal.opening_hours(d) == WEEKDAY
    assert [(n.name, n.premissa) for n in cal.notices(d)] == [("Black Friday", "P-10")]
    assert cal.notices(date(2026, 11, 26)) == []


def test_p10_black_friday_rule() -> None:
    assert black_friday(2025) == date(2025, 11, 28)
    assert black_friday(2027) == date(2027, 11, 26)


def test_p10_christmas_eve_notice(cal: StoreCalendar) -> None:
    assert [(n.name, n.premissa) for n in cal.notices(date(2026, 12, 24))] == [("Natal", "P-10")]
    assert cal.notices(date(2026, 12, 1))[0].name == "Natal"
    assert cal.notices(date(2026, 11, 30)) == []


def test_p10_august_notice_even_when_closed(cal: StoreCalendar) -> None:
    assert cal.notices(date(2026, 8, 3))[0].name == "Aniversário da Loja"
    status = cal.store_status(at(2026, 8, 26, 10))
    assert not status.is_open
    assert [n.name for n in status.notices] == ["Aniversário da Loja"]


# P-15: horas úteis


@pytest.mark.parametrize(
    ("start", "expected"),
    [
        pytest.param(at(2026, 11, 27, 17), at(2026, 12, 2, 10), id="sex-17h"),
        pytest.param(at(2026, 11, 28, 15), at(2026, 12, 2, 15), id="sab-15h"),
        pytest.param(at(2026, 11, 29, 10), at(2026, 12, 2, 15), id="dom"),
        pytest.param(at(2026, 11, 28, 12), at(2026, 12, 2, 14), id="sab-12h"),
        pytest.param(at(2026, 11, 19, 17), at(2026, 11, 25, 10), id="feriado-20-11"),
        pytest.param(at(2026, 2, 13, 17), at(2026, 2, 18, 10), id="carnaval-normal"),
    ],
)
def test_p15_add_business_hours(cal: StoreCalendar, start: datetime, expected: datetime) -> None:
    assert cal.add_business_hours(start, 24) == expected


def test_p15_ends_at_closing_time(cal: StoreCalendar) -> None:
    assert cal.add_business_hours(at(2026, 11, 30, 9), 9) == at(2026, 11, 30, 18)


def test_p15_corpus_christi_skipped(cal: StoreCalendar) -> None:
    # Qua 03/06 17h: 1 + (qui 04/06 fechado) + 9 + 4 + 9 + 1 -> ter 09/06 10h.
    assert cal.add_business_hours(at(2026, 6, 3, 17), 24) == at(2026, 6, 9, 10)


# P-20: dia útil x horas úteis


def test_p20_business_days_exclude_saturday(cal: StoreCalendar) -> None:
    assert not cal.is_business_day(date(2026, 11, 28))
    assert cal.add_business_days(date(2026, 11, 27), 1) == date(2026, 11, 30)  # sex -> seg
    assert cal.add_business_days(date(2026, 11, 19), 1) == date(2026, 11, 23)  # pula 20/11
    assert cal.is_business_day(date(2026, 2, 16))  # Carnaval não é feriado
    # Nas horas úteis o sábado conta (sex 17h + 2h = sáb 10h).
    assert cal.add_business_hours(at(2026, 11, 27, 17), 2) == at(2026, 11, 28, 10)
