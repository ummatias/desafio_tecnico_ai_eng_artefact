"""As 7 tools do agente e o registro usado pelo loop (commit 11)."""

from collections.abc import Mapping
from typing import Any

from emporio.tools.base import Tool, ToolArgs, ToolError, ToolResult
from emporio.tools.cart import QUOTE_CART
from emporio.tools.catalog import GET_PRODUCT, SEARCH_PRODUCTS
from emporio.tools.context import ToolContext, build_context
from emporio.tools.escalation import ESCALATE_TO_HUMAN
from emporio.tools.exchange import CHECK_EXCHANGE
from emporio.tools.orders import GET_ORDER
from emporio.tools.policy import GET_POLICY

TOOLS: tuple[Tool[Any], ...] = (
    SEARCH_PRODUCTS,
    GET_PRODUCT,
    QUOTE_CART,
    GET_ORDER,
    CHECK_EXCHANGE,
    GET_POLICY,
    ESCALATE_TO_HUMAN,
)
TOOLS_BY_NAME: dict[str, Tool[Any]] = {t.name: t for t in TOOLS}


def tool_schemas() -> list[dict[str, Any]]:
    return [t.schema() for t in TOOLS]


def run_tool(name: str, arguments: str | Mapping[str, Any] | None, ctx: ToolContext) -> ToolResult:
    """Executa uma tool pelo nome. Nunca lança exceção: erros voltam como dados."""
    tool = TOOLS_BY_NAME.get(name)
    if tool is None:
        return {
            "error": "unknown_tool",
            "message": f"no tool {name!r}",
            "tools": list(TOOLS_BY_NAME),
        }
    return tool.run(arguments, ctx)


__all__ = [
    "TOOLS",
    "TOOLS_BY_NAME",
    "Tool",
    "ToolArgs",
    "ToolContext",
    "ToolError",
    "ToolResult",
    "build_context",
    "run_tool",
    "tool_schemas",
]
