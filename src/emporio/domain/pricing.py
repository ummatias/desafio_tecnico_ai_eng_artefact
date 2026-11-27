"""
Preços: promoção e PIX, em centavos inteiros.

P-22: todo desconto percentual é truncado ao centavo (o preço final arredonda para cima),
nunca anunciando desconto maior que o da política (§7.1). Aplicado por unidade.
"""

PIX_DISCOUNT_PERCENT = 5  # §3: "5% de desconto sobre o preço de tabela"


def apply_discount(price_cents: int, percent: int) -> int:
    """Preço com desconto; o desconto é truncado ao centavo (P-22)."""
    if price_cents < 0:
        raise ValueError("price_cents deve ser >= 0")
    if not 0 < percent < 100:
        raise ValueError("percent deve estar entre 1 e 99")
    return price_cents - (price_cents * percent) // 100


def promotional_price(price_cents: int, discount_percent: int | None) -> int:
    """Preço de venda: com a promoção ativa, se houver."""
    if discount_percent is None:
        return price_cents
    return apply_discount(price_cents, discount_percent)


def pix_price(price_cents: int, *, has_promotion: bool) -> int | None:
    """Preço no PIX, ou None se o item tem promoção (§6.2, P-04: não cumulativo)."""
    if has_promotion:
        return None
    return apply_discount(price_cents, PIX_DISCOUNT_PERCENT)
