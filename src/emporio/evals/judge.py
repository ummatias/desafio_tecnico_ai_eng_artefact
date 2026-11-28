"""
Juiz de tom (§7.1) e de recusa, num modelo diferente do avaliado.

Opcional: sem `EVAL_JUDGE_MODEL`, tom e recusa saem como `n/d`. O juiz não muda o
pass/fail de um caso; é reportado à parte e conferido à mão por amostragem.
"""

import json
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from emporio.config import Settings
from emporio.llm import LLMClient, LLMError, Message

TONE_PASS = 4
_JSON = re.compile(r"\{.*\}", re.DOTALL)

RUBRIC = """Você avalia respostas do assistente virtual de WhatsApp de uma loja de instrumentos \
musicais. Não avalie se os fatos estão certos, só o estilo e se houve recusa.

Tom esperado (manual da loja, §7.1): informal mas profissional, acolhedor, como um amigo que \
entende de música; mensagens curtas de WhatsApp; nada robotizado nem formal demais.

Devolva só um JSON, sem texto em volta:
{"tone": <1 a 5>, "refused": <true|false>, "reason": "<uma frase>"}

- tone: 5 = exatamente o tom esperado; 3 = aceitável com problemas (longo, frio, formal); \
1 = inadequado.
- refused: true se o assistente se recusou a ajudar com o pedido do cliente por estar fora do \
escopo da loja (mesmo que com educação e oferecendo outra coisa); false se tentou atender."""


class JudgeConfigError(Exception):
    """Juiz configurado com o mesmo modelo avaliado."""


@dataclass(frozen=True)
class Verdict:
    tone: int | None
    refused: bool | None
    reason: str

    @property
    def tone_passed(self) -> bool | None:
        return None if self.tone is None else self.tone >= TONE_PASS


def _transcript(exchanges: Sequence[tuple[str, str]]) -> str:
    return "\n\n".join(f"Cliente: {user}\nAssistente: {reply}" for user, reply in exchanges)


def parse_verdict(text: str | None) -> Verdict:
    match = _JSON.search(text or "")
    if match is None:
        return Verdict(None, None, "judge answer without JSON")
    try:
        data = json.loads(match.group())
        tone = int(data["tone"])
        refused = data["refused"]
        if not 1 <= tone <= 5 or not isinstance(refused, bool):
            raise ValueError("out of range")
    except (ValueError, KeyError, TypeError) as exc:
        return Verdict(None, None, f"invalid judge JSON: {exc}")
    return Verdict(tone, refused, str(data.get("reason", "")))


class Judge:
    def __init__(self, llm: LLMClient, model: str) -> None:
        self.llm = llm
        self.model = model

    def evaluate(self, exchanges: Sequence[tuple[str, str]]) -> Verdict:
        messages = [Message.system(RUBRIC), Message.user(_transcript(exchanges))]
        try:
            response = self.llm.complete(messages, [])
        except LLMError as exc:
            return Verdict(None, None, f"judge failed: {type(exc).__name__}")
        return parse_verdict(response.text)


def make_judge(settings: Settings, factory: Callable[[Settings], LLMClient]) -> Judge | None:
    model = settings.eval_judge_model
    if not model:
        return None
    if model == settings.llm_model:
        raise JudgeConfigError("EVAL_JUDGE_MODEL must differ from LLM_MODEL")
    judge_settings = settings.model_copy(update={"llm_model": model})
    return Judge(factory(judge_settings), model)
