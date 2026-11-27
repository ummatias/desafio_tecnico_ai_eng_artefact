"""
    Uma linha JSONL por turno. 
    O registro já chega mascarado
    
    Apenas escrita
"""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from emporio.config import Settings


class TraceWriter:
    def __init__(self, path: Path, static: Mapping[str, Any] | None = None) -> None:
        self.path = path
        # Campos iguais em todo turno (ex.: REFERENCE_DATE configurada)
        self.static = dict(static or {})

    @classmethod
    def from_settings(cls, settings: Settings) -> "TraceWriter | None":
        if not settings.trace_enabled:
            return None
        ref = settings.reference_date
        return cls(settings.trace_path, {"reference_date": ref.isoformat() if ref else None})

    def write(self, record: Mapping[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps({**self.static, **record}, ensure_ascii=False, default=str)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
