"""
Trocas, devoluções e garantia.

Só fonte confiável decide (P-17): a data da compra (`order_date`) e o evento de entrega do
rastreio. A data informada pelo cliente vai para o ticket, nunca para a conta.

    - P-24: a data da compra pode conceder um direito, nunca negá-lo (recebimento >= compra).
    - P-25: o §4.4 bloqueia só a troca por preferência; no arrependimento, encaminha à equipe.

Prazos em dias corridos, fechados no fim: o 7º dia está dentro, o 8º fora.
"""

from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import Literal, Protocol

Reason = Literal["regret", "preference", "defect"]
Outcome = Literal["eligible", "expired", "not_eligible", "to_confirm", "ask", "not_applicable"]
Route = Literal[
    "return", "preference_exchange", "store_exchange", "legal_warranty", "manufacturer_warranty"
]
Basis = Literal["tracking", "purchase"]
Question = Literal["custom_setup", "final_sale", "mouthpiece"]

REGRET_DAYS = 7  # §4.1: 7 dias corridos após o recebimento
PREFERENCE_DAYS = 7  # §4.3: 7 dias, marco = recebimento (P-16)
STORE_DEFECT_DAYS = 30  # §4.2: 30 dias corridos após a compra
LEGAL_WARRANTY_DAYS = 90  # §8.1: 90 dias a partir do recebimento
WIND_CATEGORIES = (6, 7)  # §4.4: categoria de sopro


class ReceiptDateSource(Protocol):
    """Fonte confiável da data de recebimento (evento de entrega do rastreio)."""

    def delivered_on(self, order_id: int, tracking_code: str | None) -> date | None: ...


@dataclass(frozen=True)
class ExchangeRequest:
    order_id: int
    order_date: date
    order_status: str
    category_id: int
    reason: Reason
    today: date
    receipt_date: date | None = None  # só de fonte confiável (ReceiptDateSource)
    stated_receipt_date: date | None = None  # informada pelo cliente: só para o ticket
    custom_setup: bool | None = None  # §4.4, respostas do cliente
    final_sale: bool | None = None
    mouthpiece: bool | None = None


@dataclass(frozen=True)
class ExchangeDecision:
    outcome: Outcome
    reason: Reason
    code: str
    sections: tuple[str, ...]
    assumptions: tuple[str, ...] = ()
    route: Route | None = None
    basis: Basis | None = None
    deadline: date | None = None  # com base "purchase", o prazo vai pelo menos até esta data
    escalate: bool = False
    questions: tuple[Question, ...] = ()
    needs_stock: bool = False
    alternatives: tuple[str, ...] = ()
    stated_receipt_date: date | None = None


@dataclass(frozen=True)
class _Window:
    state: Literal["open", "closed", "unknown"]
    basis: Basis | None = None
    deadline: date | None = None


def _receipt_window(req: ExchangeRequest, days: int) -> _Window:
    """Prazo contado do recebimento. Sem rastreio, a compra só pode abri-lo (P-24)."""
    if req.receipt_date is not None:
        end = req.receipt_date + timedelta(days=days)
        return _Window("open" if req.today <= end else "closed", "tracking", end)
    end = req.order_date + timedelta(days=days)
    if req.today <= end:
        return _Window("open", "purchase", end)
    return _Window("unknown")


def _section_4_4(req: ExchangeRequest) -> tuple[bool, tuple[Question, ...]]:
    """(excluído, perguntas pendentes). Um "sim" basta para excluir (P-21, P-25)."""
    answers: dict[Question, bool | None] = {
        "custom_setup": req.custom_setup,
        "final_sale": req.final_sale,
    }
    if req.category_id in WIND_CATEGORIES:
        answers["mouthpiece"] = req.mouthpiece
    if any(answers.values()):
        return True, ()
    return False, tuple(q for q, a in answers.items() if a is None)


def _validate(req: ExchangeRequest) -> None:
    if req.today < req.order_date:
        raise ValueError("today is before the purchase date")
    if req.receipt_date is not None and req.receipt_date < req.order_date:
        raise ValueError("receipt date is before the purchase date")


def evaluate(req: ExchangeRequest) -> ExchangeDecision:
    _validate(req)
    if req.order_status != "delivered":
        code = "order_cancelled" if req.order_status == "cancelled" else "order_not_delivered"
        return ExchangeDecision("not_applicable", req.reason, code, ("4",))
    if req.reason == "defect":
        return _defect(req)
    return _regret_or_preference(req)


def _regret_or_preference(req: ExchangeRequest) -> ExchangeDecision:
    regret = req.reason == "regret"
    section = "4.1" if regret else "4.3"
    window = _receipt_window(req, REGRET_DAYS if regret else PREFERENCE_DAYS)
    base = ExchangeDecision(
        outcome="eligible",
        reason=req.reason,
        code="within_window",
        sections=(section,),
        assumptions=("P-11" if regret else "P-16", "P-17", "P-24", "P-25"),
        route="return" if regret else "preference_exchange",
        basis=window.basis,
        deadline=window.deadline,
        stated_receipt_date=req.stated_receipt_date,
    )

    if window.state == "closed":
        return replace(base, outcome="expired", code="window_closed", alternatives=("defect",))
    if window.state == "unknown":
        return replace(base, outcome="to_confirm", code="no_receipt_date", escalate=True)

    excluded, questions = _section_4_4(req)
    with_4_4 = (section, "4.4")
    if excluded and regret:
        # P-25: o §4.4 não nega o arrependimento (CDC art. 49); a equipe decide.
        return replace(
            base,
            outcome="to_confirm",
            code="section_4_4_reported",
            sections=with_4_4,
            escalate=True,
        )
    if excluded:
        return replace(base, outcome="not_eligible", code="section_4_4", sections=with_4_4)
    if questions:
        return replace(
            base,
            outcome="ask",
            code="section_4_4_pending",
            sections=with_4_4,
            questions=questions,
        )
    return replace(base, needs_stock=not regret)


def _defect(req: ExchangeRequest) -> ExchangeDecision:
    """P-01: troca na loja (§4.2), garantia legal (§8.1), garantia do fabricante (§8.2).

    O §4.4 não se aplica nem é perguntado (P-25).
    """
    assumptions = ("P-01", "P-17", "P-24", "P-25")
    store_end = req.order_date + timedelta(days=STORE_DEFECT_DAYS)
    if req.today <= store_end:
        return ExchangeDecision(
            "eligible",
            "defect",
            "store_exchange",
            ("4.2",),
            assumptions,
            route="store_exchange",
            basis="purchase",
            deadline=store_end,
            stated_receipt_date=req.stated_receipt_date,
        )
    window = _receipt_window(req, LEGAL_WARRANTY_DAYS)
    if window.state == "open":
        return ExchangeDecision(
            "eligible",
            "defect",
            "legal_warranty",
            ("4.2", "8.1"),
            assumptions,
            route="legal_warranty",
            basis=window.basis,
            deadline=window.deadline,
            escalate=True,
            stated_receipt_date=req.stated_receipt_date,
        )
    if window.state == "closed":
        return ExchangeDecision(
            "expired",
            "defect",
            "legal_warranty_expired",
            ("8.1", "8.2"),
            assumptions,
            route="manufacturer_warranty",
            basis=window.basis,
            deadline=window.deadline,
            alternatives=("store_mediation",),
            stated_receipt_date=req.stated_receipt_date,
        )
    # Nunca garantia do fabricante sem fonte confiável (P-24).
    return ExchangeDecision(
        "to_confirm",
        "defect",
        "no_receipt_date",
        ("8.1", "8.2"),
        assumptions,
        escalate=True,
        stated_receipt_date=req.stated_receipt_date,
    )
