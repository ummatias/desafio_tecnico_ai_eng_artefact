import pytest

from emporio.config import Settings
from emporio.evals.judge import Judge, JudgeConfigError, make_judge, parse_verdict
from emporio.llm import LLMClient, LLMUnavailable
from emporio.llm.fake import FakeLLMClient, text_response


def test_parse_valid_with_fences() -> None:
    verdict = parse_verdict('```json\n{"tone": 4, "refused": false, "reason": "ok"}\n```')
    assert (verdict.tone, verdict.refused, verdict.tone_passed) == (4, False, True)


@pytest.mark.parametrize(
    "text", [None, "sem json", '{"tone": 9, "refused": false}', '{"tone": 3, "refused": "no"}']
)
def test_parse_invalid_is_na(text: str | None) -> None:
    verdict = parse_verdict(text)
    assert verdict.tone is None and verdict.refused is None and verdict.tone_passed is None


def test_judge_sends_rubric_and_transcript() -> None:
    llm = FakeLLMClient([text_response('{"tone": 5, "refused": true, "reason": "x"}')])
    verdict = Judge(llm, "j").evaluate([("tem cordas?", "Só instrumentos.")])
    assert verdict.refused is True
    (request,) = llm.requests
    assert request.tools == ()
    assert "§7.1" in (request.messages[0].content or "")
    assert "Cliente: tem cordas?" in (request.messages[1].content or "")


def test_judge_llm_error_is_na() -> None:
    verdict = Judge(FakeLLMClient([LLMUnavailable("x")]), "j").evaluate([("a", "b")])
    assert verdict.tone is None and "LLMUnavailable" in verdict.reason


def test_make_judge() -> None:
    seen: list[str] = []

    def factory(settings: Settings) -> LLMClient:
        seen.append(settings.llm_model)
        return FakeLLMClient([])

    assert make_judge(Settings(eval_judge_model=None), factory) is None
    judge = make_judge(Settings(llm_model="a/x", eval_judge_model="b/y"), factory)
    assert judge is not None and judge.model == "b/y" and seen == ["b/y"]
    with pytest.raises(JudgeConfigError):
        make_judge(Settings(llm_model="a/x", eval_judge_model="a/x"), factory)
