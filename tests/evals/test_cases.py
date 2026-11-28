import csv
from datetime import datetime
from pathlib import Path

import pytest

from emporio.db.derived import normalize_phone
from emporio.evals.cases import CaseError, load_case, load_cases
from tests.conftest import DATA_DIR, ROOT

CASES_DIR = ROOT / "evals" / "cases"


def _phones() -> set[str | None]:
    with (DATA_DIR / "customers.csv").open(encoding="utf-8") as fh:
        return {normalize_phone(row["phone"]) for row in csv.DictReader(fh)}


def test_repository_cases_load() -> None:
    cases = load_cases(CASES_DIR)
    assert len(cases) >= 3
    assert len({c.id for c in cases}) == len(cases)


def test_repository_case_phones_exist() -> None:
    phones = _phones()
    for case in load_cases(CASES_DIR):
        if case.session.phone is not None:
            assert normalize_phone(case.session.phone) in phones, case.id


def test_date_only_means_ten_o_clock(tmp_path: Path) -> None:
    path = tmp_path / "c.yaml"
    path.write_text(
        "id: c\ncategory: hours\nsource: §2\nreference_date: 2026-11-26\nturns: [{user: oi}]\n",
        encoding="utf-8",
    )
    assert load_case(path).reference_date == datetime(2026, 11, 26, 10, 0)


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("id: outro\n", "differs from the file name"),
        ("id: c\nexpected_tools: [nao_existe]\n", "unknown tools"),
        ("id: c\nexpected_outcome: {outcome: talvez}\n", "unknown outcome"),
        ("id: c\ncampo_extra: 1\n", "Extra inputs"),
        ("id: c\nturns: [\n", "c.yaml"),
    ],
)
def test_invalid_cases(tmp_path: Path, body: str, message: str) -> None:
    base = "category: hours\nsource: §2\nreference_date: 2026-11-26\nturns: [{user: oi}]\n"
    path = tmp_path / "c.yaml"
    path.write_text(base + body if "turns: [\n" not in body else body, encoding="utf-8")
    with pytest.raises(CaseError, match=message):
        load_case(path)


def test_only_filters_and_rejects_unknown(tmp_path: Path) -> None:
    for name in ("a", "b"):
        (tmp_path / f"{name}.yaml").write_text(
            f"id: {name}\ncategory: hours\nsource: §2\nreference_date: 2026-11-26\n"
            "turns: [{user: oi}]\n",
            encoding="utf-8",
        )
    assert [c.id for c in load_cases(tmp_path, {"b"})] == ["b"]
    with pytest.raises(CaseError, match="unknown case ids"):
        load_cases(tmp_path, {"z"})


def test_empty_dir(tmp_path: Path) -> None:
    with pytest.raises(CaseError, match="no cases"):
        load_cases(tmp_path)
