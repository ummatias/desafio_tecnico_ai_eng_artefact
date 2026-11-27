"""get_policy: uma seção do manual por ID, com as anotações e o texto das premissas (D-24)."""

from pydantic import Field

from emporio.tools.base import Tool, ToolArgs, ToolError, ToolResult
from emporio.tools.context import ToolContext

ANNOTATIONS_NOTE = (
    "'text' is the manual verbatim; 'annotations' and 'assumptions' are not manual text, and "
    "where an assumption exists it prevails over the literal reading"
)


class GetPolicyArgs(ToolArgs):
    section_id: str = Field(
        max_length=10, description="Manual section number, e.g. '4.1', '8.1', '3.1'"
    )


def get_policy(args: GetPolicyArgs, ctx: ToolContext) -> ToolResult:
    section_id = args.section_id.strip().removeprefix("§")
    section = ctx.policies.sections.get(section_id)
    if section is None:
        raise ToolError(
            "unknown_section",
            f"no section {args.section_id!r}",
            sections={s.id: s.title for s in ctx.policies.sections.values()},
        )
    return {
        "section_id": section.id,
        "title": section.title,
        "text": section.text,
        "annotations": list(section.annotations),
        "assumptions": [
            {"id": a.id, "title": a.title, "status": a.status, "premise": a.premise}
            for a in (ctx.policies.assumptions[i] for i in section.assumption_ids)
        ],
        "note": ANNOTATIONS_NOTE,
    }


GET_POLICY = Tool(
    name="get_policy",
    description="One section of the store policy manual by number, with its assumptions.",
    args_model=GetPolicyArgs,
    handler=get_policy,
)
