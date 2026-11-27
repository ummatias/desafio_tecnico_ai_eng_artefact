import json

import pytest
from sqlalchemy import Engine, func, select

from emporio.agent import MAX_ITERATIONS, run_turn
from emporio.agent.loop import FORCED_ANSWER_INSTRUCTION, SAFE_REPLY_WITHOUT_PROTOCOL
from emporio.db.schema import tickets
from emporio.llm import LLMTruncated, LLMUnavailable, Message, Response, ToolCall
from emporio.llm.fake import FakeLLMClient, text_response, tool_call_response
from emporio.tools import ToolContext
from tests.tools.conftest import ANA, make_ctx

SEARCH = tool_call_response("search_products", {"query": "takamine gd 20"})


def _ctx(engine: Engine, phone: str | None = ANA) -> ToolContext:
    return make_ctx(engine, phone)


def _ticket_count(engine: Engine) -> int:
    with engine.connect() as conn:
        return int(conn.execute(select(func.count()).select_from(tickets)).scalar_one())


def _tool_payload(message: Message) -> dict[str, object]:
    assert message.role == "tool" and message.content is not None
    payload: dict[str, object] = json.loads(message.content)
    return payload


def test_direct_answer(fresh_engine: Engine) -> None:
    llm = FakeLLMClient([text_response("  Oi, Ana! Como posso ajudar?  ")])
    result = run_turn(llm, _ctx(fresh_engine), [], "oi")
    assert result.reply == "Oi, Ana! Como posso ajudar?"
    assert result.stop_reason == "answer"
    assert result.iterations == 1
    assert not result.escalated and result.protocol is None
    assert _ticket_count(fresh_engine) == 0


def test_request_shape(fresh_engine: Engine) -> None:
    history = [Message.user("oi"), Message("assistant", "Oi! Como posso ajudar?")]
    llm = FakeLLMClient([text_response("ok")])
    run_turn(llm, _ctx(fresh_engine), history, "tem violão?")
    (request,) = llm.requests
    assert request.messages[0].role == "system"
    assert "Empório da Música" in (request.messages[0].content or "")
    assert request.messages[1:3] == tuple(history)
    assert request.messages[3] == Message.user("tem violão?")
    assert {t["name"] for t in request.tools} == {
        "search_products",
        "get_product",
        "quote_cart",
        "get_order",
        "check_exchange",
        "get_policy",
        "escalate_to_human",
    }


def test_tool_then_answer_with_envelope(fresh_engine: Engine) -> None:
    llm = FakeLLMClient([SEARCH, text_response("Tenho o GD20!")])
    result = run_turn(llm, _ctx(fresh_engine), [], "tem takamine gd 20?")
    assert result.reply == "Tenho o GD20!"
    assert [r.name for r in result.tool_runs] == ["search_products"]
    second = llm.requests[1].messages
    assert second[-2].role == "assistant" and second[-2].tool_calls == SEARCH.tool_calls
    payload = _tool_payload(second[-1])
    assert second[-1].tool_call_id == "call_1"
    assert payload["tool"] == "search_products"
    assert payload["untrusted_data"] is True
    assert "GD20" in json.dumps(payload["data"])


def test_two_calls_in_one_response(fresh_engine: Engine) -> None:
    both = Response(
        text=None,
        tool_calls=(
            ToolCall("a", "get_policy", json.dumps({"section_id": "2"})),
            ToolCall("b", "get_order", json.dumps({"order_id": 8})),
        ),
        finish_reason="tool_calls",
    )
    llm = FakeLLMClient([both, text_response("pronto")])
    result = run_turn(llm, _ctx(fresh_engine), [], "horário e meu pedido 8")
    assert [r.name for r in result.tool_runs] == ["get_policy", "get_order"]
    tool_messages = [m for m in llm.requests[1].messages if m.role == "tool"]
    assert [m.tool_call_id for m in tool_messages] == ["a", "b"]


def test_tool_errors_come_back_as_data(fresh_engine: Engine) -> None:
    llm = FakeLLMClient(
        [
            tool_call_response("search_products", "{not json"),
            tool_call_response("does_not_exist", {}, call_id="call_2"),
            text_response("Pode repetir?"),
        ]
    )
    result = run_turn(llm, _ctx(fresh_engine), [], "?")
    assert result.stop_reason == "answer"
    assert [r.error for r in result.tool_runs] == ["invalid_arguments", "unknown_tool"]
    payload = _tool_payload(llm.requests[2].messages[-1])
    assert payload["data"] == result.tool_runs[1].result


def test_forced_answer_after_max_iterations(fresh_engine: Engine) -> None:
    llm = FakeLLMClient([SEARCH] * MAX_ITERATIONS + [text_response("Achei o GD20.")])
    result = run_turn(llm, _ctx(fresh_engine), [], "tem takamine?")
    assert result.stop_reason == "forced_answer"
    assert result.reply == "Achei o GD20."
    assert not result.escalated
    assert _ticket_count(fresh_engine) == 0
    assert len(llm.requests) == MAX_ITERATIONS + 1
    forced = llm.requests[-1]
    assert forced.tools == ()
    assert forced.messages[-1] == Message.system(FORCED_ANSWER_INSTRUCTION)


def test_max_iterations_then_empty_opens_ticket(fresh_engine: Engine) -> None:
    llm = FakeLLMClient([SEARCH] * MAX_ITERATIONS + [text_response("   ")])
    result = run_turn(llm, _ctx(fresh_engine), [], "tem takamine?")
    assert result.stop_reason == "max_iterations"
    assert len(llm.requests) == MAX_ITERATIONS + 1
    assert result.escalated and result.protocol is not None
    assert result.protocol in result.reply
    assert _ticket_count(fresh_engine) == 1
    assert result.tool_runs[-1].by == "code"


def test_forced_call_returning_tools_opens_ticket(fresh_engine: Engine) -> None:
    llm = FakeLLMClient([SEARCH] * (MAX_ITERATIONS + 1))
    result = run_turn(llm, _ctx(fresh_engine), [], "tem takamine?")
    assert result.stop_reason == "max_iterations"
    assert result.escalated
    assert sum(r.name == "search_products" for r in result.tool_runs) == MAX_ITERATIONS


def test_empty_answer_then_forced_text(fresh_engine: Engine) -> None:
    llm = FakeLLMClient([text_response(""), text_response("Posso ajudar com instrumentos!")])
    result = run_turn(llm, _ctx(fresh_engine), [], "oi")
    assert result.stop_reason == "forced_answer"
    assert result.reply == "Posso ajudar com instrumentos!"
    assert _ticket_count(fresh_engine) == 0


def test_empty_answer_twice_opens_ticket(fresh_engine: Engine) -> None:
    llm = FakeLLMClient([text_response(""), text_response("")])
    result = run_turn(llm, _ctx(fresh_engine), [], "oi")
    assert result.stop_reason == "empty_answer"
    assert result.escalated
    assert _ticket_count(fresh_engine) == 1


@pytest.mark.parametrize("error", [LLMUnavailable("down"), LLMTruncated("length")])
def test_llm_error_opens_ticket_without_forced_call(fresh_engine: Engine, error: Exception) -> None:
    llm = FakeLLMClient([SEARCH, error])  # type: ignore[list-item]
    result = run_turn(llm, _ctx(fresh_engine), [], "tem takamine?")
    assert result.stop_reason == "llm_error"
    assert result.llm_error == type(error).__name__
    assert len(llm.requests) == 2
    assert result.escalated and result.protocol in result.reply  # type: ignore[operator]
    assert _ticket_count(fresh_engine) == 1


def test_forced_call_error_opens_ticket(fresh_engine: Engine) -> None:
    llm = FakeLLMClient([*[SEARCH] * MAX_ITERATIONS, LLMUnavailable("down")])
    result = run_turn(llm, _ctx(fresh_engine), [], "tem takamine?")
    assert result.stop_reason == "max_iterations"
    assert result.llm_error == "LLMUnavailable"
    assert _ticket_count(fresh_engine) == 1


def test_model_escalation_is_reused(fresh_engine: Engine) -> None:
    escalate = tool_call_response(
        "escalate_to_human", {"summary": "Reclamação", "category": "complaint"}
    )
    llm = FakeLLMClient([escalate, *[SEARCH] * (MAX_ITERATIONS - 1), text_response("")])
    result = run_turn(llm, _ctx(fresh_engine), [], "quero reclamar")
    assert _ticket_count(fresh_engine) == 1
    assert result.escalated
    assert result.protocol == result.tool_runs[0].result["protocol"]
    assert result.protocol in result.reply
    assert all(r.by == "model" for r in result.tool_runs)


def test_model_escalation_flags_turn(fresh_engine: Engine) -> None:
    escalate = tool_call_response(
        "escalate_to_human", {"summary": "Reclamação", "category": "complaint"}
    )
    llm = FakeLLMClient([escalate, text_response("Chamado aberto!")])
    result = run_turn(llm, _ctx(fresh_engine), [], "quero reclamar")
    assert result.stop_reason == "answer"
    assert result.escalated and result.protocol is not None


def test_escalation_failure_gives_safe_reply(fresh_engine: Engine) -> None:
    """Sem tabela de chamados, a tool falha: resposta segura sem protocolo."""
    tickets.drop(fresh_engine)
    llm = FakeLLMClient([LLMUnavailable("down")])
    result = run_turn(llm, _ctx(fresh_engine), [], "oi")
    assert result.reply == SAFE_REPLY_WITHOUT_PROTOCOL
    assert not result.escalated
    assert result.tool_runs[-1].error == "internal_error"


def test_transcript(fresh_engine: Engine) -> None:
    llm = FakeLLMClient([SEARCH, text_response("Tenho!")])
    result = run_turn(llm, _ctx(fresh_engine), [], "tem takamine?")
    assert result.transcript == (Message.user("tem takamine?"), Message("assistant", "Tenho!"))
