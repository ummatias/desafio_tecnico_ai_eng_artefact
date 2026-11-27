"""Tools no formato de function calling da OpenAI, sem `$ref`."""

from collections.abc import Mapping, Sequence
from typing import Any

from emporio.llm.types import ToolSchema


def inline_refs(schema: Mapping[str, Any]) -> dict[str, Any]:
    defs: Mapping[str, Any] = schema.get("$defs", {})

    def resolve(node: Any, seen: tuple[str, ...]) -> Any:
        if isinstance(node, Mapping):
            ref = node.get("$ref")
            if isinstance(ref, str):
                name = ref.removeprefix("#/$defs/")
                if name not in defs or name in seen:
                    raise ValueError(f"$ref não suportado: {ref}")
                rest = {k: v for k, v in node.items() if k != "$ref"}
                return {**resolve(defs[name], (*seen, name)), **resolve(rest, seen)}
            return {k: resolve(v, seen) for k, v in node.items() if k != "$defs"}
        if isinstance(node, list):
            return [resolve(item, seen) for item in node]
        return node

    result: dict[str, Any] = resolve(schema, ())
    return result


def openai_tools(schemas: Sequence[ToolSchema]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": s["name"],
                "description": s["description"],
                "parameters": inline_refs(s["parameters"]),
            },
        }
        for s in schemas
    ]
