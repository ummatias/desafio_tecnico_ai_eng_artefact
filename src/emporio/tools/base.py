"""
Base das tools: argumentos validados, erros como dados, nunca exceção para o modelo.

Cada tool recebe argumentos pydantic e um `ToolContext`, e devolve um dict compacto. Um erro
esperado é `ToolError`; `run_tool` converte qualquer falha em `{"error": ..., "message": ...}`.
"""

import json
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from emporio.tools.context import ToolContext

logger = logging.getLogger(__name__)

ToolResult = dict[str, Any]


class ToolArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ToolError(Exception):
    """Erro esperado, devolvido ao modelo como dado."""

    def __init__(self, code: str, message: str, **details: Any) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details

    def as_result(self) -> ToolResult:
        return {"error": self.code, "message": self.message, **self.details}


@dataclass(frozen=True)
class Tool[ArgsT: ToolArgs]:
    name: str
    description: str
    args_model: type[ArgsT]
    handler: Callable[[ArgsT, ToolContext], ToolResult]

    def schema(self) -> dict[str, Any]:
        """Nome, descrição e JSON schema dos argumentos (formato de function calling)."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.args_model.model_json_schema(),
        }

    def run(self, arguments: str | Mapping[str, Any] | None, ctx: ToolContext) -> ToolResult:
        try:
            raw = json.loads(arguments) if isinstance(arguments, str) else dict(arguments or {})
        except json.JSONDecodeError as exc:
            return {"error": "invalid_arguments", "message": f"arguments are not JSON: {exc.msg}"}
        try:
            args = self.args_model.model_validate(raw)
        except ValidationError as exc:
            problems = [
                {"field": ".".join(str(p) for p in err["loc"]) or "(root)", "message": err["msg"]}
                for err in exc.errors()
            ]
            return {
                "error": "invalid_arguments",
                "message": "invalid arguments",
                "problems": problems,
            }
        try:
            return self.handler(args, ctx)
        except ToolError as exc:
            return exc.as_result()
        except Exception:
            logger.exception("tool %s failed", self.name)
            return {"error": "internal_error", "message": "the tool failed; escalate if needed"}
