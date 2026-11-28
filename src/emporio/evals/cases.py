"""
Schema dos casos de avaliação (`evals/cases/<id>.yaml`).

Os fatos esperados são literais escritos à mão a partir da política e dos CSVs, nunca
calculados com `emporio.domain` ou `emporio.tools`: um eval não pode herdar um bug do código
que ele avalia.
"""

from datetime import date, datetime, time
from pathlib import Path
from typing import Literal, get_args

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from emporio.domain.exchange import Outcome
from emporio.tools import TOOLS_BY_NAME

Category = Literal[
    "product",
    "cart",
    "payment",
    "order",
    "exchange",
    "hours",
    "promo",
    "scope",
    "security",
    "escalation",
]
DEFAULT_TIME = time(10)


class CaseError(Exception):
    """Arquivo de caso inválido."""


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AnyOf(_Model):
    any_of: tuple[str, ...] = Field(min_length=1)


Fact = str | AnyOf


class Turn(_Model):
    user: str = Field(min_length=1)
    expected_facts: tuple[Fact, ...] = ()
    must_not_include: tuple[str, ...] = ()


class Session(_Model):
    phone: str | None = None
    tracking_source: Literal["none", "fixture"] = "none"


class ExpectedOutcome(_Model):
    tool: Literal["check_exchange"] = "check_exchange"
    outcome: str
    sections: tuple[str, ...] = ()

    @field_validator("outcome")
    @classmethod
    def _known(cls, value: str) -> str:
        if value not in get_args(Outcome):
            raise ValueError(f"unknown outcome {value!r}")
        return value


def _tool_names(names: tuple[str, ...]) -> tuple[str, ...]:
    unknown = [n for n in names if n not in TOOLS_BY_NAME]
    if unknown:
        raise ValueError(f"unknown tools: {unknown}")
    return names


class EvalCase(_Model):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    category: Category
    source: str = Field(min_length=1, description="Seções/premissas de onde vêm os fatos")
    reference_date: datetime
    session: Session = Session()
    turns: tuple[Turn, ...] = Field(min_length=1)
    expected_tools: tuple[str, ...] = ()
    forbidden_tools: tuple[str, ...] = ()
    expected_outcome: ExpectedOutcome | None = None
    must_not_include: tuple[str, ...] = ()
    should_escalate: bool | None = None
    should_refuse: bool | None = None

    @field_validator("reference_date", mode="before")
    @classmethod
    def _date_only_at_ten(cls, value: object) -> object:
        if isinstance(value, date) and not isinstance(value, datetime):
            return datetime.combine(value, DEFAULT_TIME)
        return value

    @field_validator("expected_tools", "forbidden_tools")
    @classmethod
    def _tools(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _tool_names(value)


def load_case(path: Path) -> EvalCase:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        case = EvalCase.model_validate(raw)
    except (yaml.YAMLError, ValidationError) as exc:
        raise CaseError(f"{path.name}: {exc}") from exc
    if case.id != path.stem:
        raise CaseError(f"{path.name}: id {case.id!r} differs from the file name")
    return case


def load_cases(directory: Path, only: set[str] | None = None) -> list[EvalCase]:
    cases = [load_case(p) for p in sorted(directory.glob("*.yaml"))]
    if only:
        missing = only - {c.id for c in cases}
        if missing:
            raise CaseError(f"unknown case ids: {sorted(missing)}")
        cases = [c for c in cases if c.id in only]
    if not cases:
        raise CaseError(f"no cases in {directory}")
    return cases
