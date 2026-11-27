from datetime import datetime

import pytest
from sqlalchemy import Engine

from emporio.clock import store_now
from emporio.config import Settings
from emporio.repositories import CustomerRepository
from emporio.tools import TOOLS, Tool, ToolArgs, ToolContext, build_context, run_tool, tool_schemas
from tests.tools.conftest import ANA, TZ, MakeCtx

EXPECTED = [
    "search_products",
    "get_product",
    "quote_cart",
    "get_order",
    "check_exchange",
    "get_policy",
    "escalate_to_human",
]


def test_seven_tools_with_schemas() -> None:
    schemas = tool_schemas()
    assert [s["name"] for s in schemas] == EXPECTED
    for s in schemas:
        assert s["description"]
        assert s["parameters"]["type"] == "object"


def test_no_tool_takes_customer_id() -> None:
    for tool in TOOLS:
        assert "customer_id" not in tool.args_model.model_fields


def test_unknown_tool(ctx_for: MakeCtx) -> None:
    assert run_tool("buscar_produtos", {}, ctx_for())["error"] == "unknown_tool"


def test_arguments_as_json_string(ctx_for: MakeCtx) -> None:
    assert run_tool("get_product", '{"product_id": 95}', ctx_for())["name"].startswith("Takamine")


@pytest.mark.parametrize(
    "arguments",
    ['{"product_id": ', {"product_id": "abc"}, {"product_id": 95, "extra": 1}, None],
)
def test_invalid_arguments_never_raise(ctx_for: MakeCtx, arguments: object) -> None:
    result = run_tool("get_product", arguments, ctx_for())  # type: ignore[arg-type]
    assert result["error"] == "invalid_arguments"


def test_unexpected_exception_becomes_internal_error(ctx_for: MakeCtx) -> None:
    def boom(args: ToolArgs, ctx: ToolContext) -> dict[str, object]:
        raise RuntimeError("database is gone")

    tool = Tool(name="boom", description="x", args_model=ToolArgs, handler=boom)
    result = tool.run({}, ctx_for())
    assert result["error"] == "internal_error"
    assert "database" not in result["message"]


def test_build_context_from_settings(seeded_engine: Engine) -> None:
    settings = Settings(_env_file=None, reference_date="2026-11-26")
    customer = CustomerRepository(seeded_engine).get_by_phone(ANA)
    ctx = build_context(settings, seeded_engine, customer)
    assert ctx.now == datetime(2026, 11, 26, 10, 0, tzinfo=TZ)
    assert run_tool("get_order", {"order_id": 8}, ctx)["order"]["delivery_state"] == "late"


def test_store_now_with_time() -> None:
    settings = Settings(_env_file=None, reference_date="2026-11-26T17:30")
    assert store_now(settings) == datetime(2026, 11, 26, 17, 30, tzinfo=TZ)
    real = store_now(Settings(_env_file=None))
    assert real.tzinfo is not None
