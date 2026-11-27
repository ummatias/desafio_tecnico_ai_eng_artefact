"""
Manual (`knowledge/policies.md`) e premissas (`docs/assumptions.md`) lidos por seção (D-24).

Cada seção traz a citação do manual sem os `>`, as anotações (`Marco`, `Premissas`) e o texto
das premissas citadas. Uma premissa citada e inexistente é erro de carga.
"""

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

SECTION_RE = re.compile(r"^## (\d+(?:\.\d+)*) (.+)$")
ASSUMPTION_RE = re.compile(r"^### (P-\d{2}) · (.+)$")
ASSUMPTION_ID_RE = re.compile(r"\bP-\d{2}\b")
PAGE_RE = re.compile(r"^Página \d+\.$")
FIELD_RE = re.compile(r"^(ID|Seção|Status|Teste|Premissa|Motivo):\s*(.*)$")


class PolicyConfigError(Exception):
    """Manual ou premissas com formato inválido."""


@dataclass(frozen=True)
class Assumption:
    id: str
    title: str
    status: str
    premise: str


@dataclass(frozen=True)
class PolicySection:
    id: str
    title: str
    text: str
    annotations: tuple[str, ...]
    assumption_ids: tuple[str, ...]


@dataclass(frozen=True)
class PolicyBook:
    sections: dict[str, PolicySection]
    assumptions: dict[str, Assumption]


def _blocks(lines: list[str], heading: re.Pattern[str]) -> list[tuple[re.Match[str], list[str]]]:
    """Corpo de cada cabeçalho `heading`; qualquer outro cabeçalho encerra o bloco."""
    blocks: list[tuple[re.Match[str], list[str]]] = []
    current: list[str] | None = None
    for line in lines:
        match = heading.match(line)
        if match:
            current = []
            blocks.append((match, current))
        elif line.startswith("#"):
            current = None
        elif current is not None:
            current.append(line)
    return blocks


def _section(match: re.Match[str], body: list[str]) -> PolicySection:
    quote: list[str] = []
    annotations: list[str] = []
    for raw in body:
        line = raw.rstrip()
        if line.startswith(">"):
            quote.append(line[1:].removeprefix(" "))
        elif not line.strip() or PAGE_RE.match(line.strip()):
            continue
        elif line.startswith("**") or not annotations:
            annotations.append(line.strip())
        else:
            annotations[-1] += " " + line.strip()  # linha quebrada da anotação anterior
    joined = " ".join(annotations)
    ids = tuple(dict.fromkeys(ASSUMPTION_ID_RE.findall(joined)))
    return PolicySection(
        match[1], match[2].strip(), "\n".join(quote).strip(), tuple(annotations), ids
    )


def _assumption(match: re.Match[str], body: list[str]) -> Assumption:
    fields: dict[str, str] = {}
    current: str | None = None
    for raw in body:
        line = raw.strip()
        field = FIELD_RE.match(line)
        if field:
            current = field[1]
            fields[current] = field[2]
        elif line and current is not None:
            fields[current] += " " + line
        else:
            current = None
    if "Premissa" not in fields or "Status" not in fields:
        raise PolicyConfigError(f"{match[1]}: sem Premissa ou Status")
    return Assumption(match[1], match[2].strip(), fields["Status"], fields["Premissa"])


@lru_cache
def load_policy_book(policies_path: Path, assumptions_path: Path) -> PolicyBook:
    try:
        policy_lines = policies_path.read_text(encoding="utf-8").splitlines()
        assumption_lines = assumptions_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise PolicyConfigError(str(exc)) from exc
    sections = {s.id: s for s in (_section(m, b) for m, b in _blocks(policy_lines, SECTION_RE))}
    assumptions = {
        a.id: a for a in (_assumption(m, b) for m, b in _blocks(assumption_lines, ASSUMPTION_RE))
    }
    for section in sections.values():
        missing = [i for i in section.assumption_ids if i not in assumptions]
        if missing:
            raise PolicyConfigError(f"seção {section.id} cita premissas inexistentes: {missing}")
    return PolicyBook(sections, assumptions)
