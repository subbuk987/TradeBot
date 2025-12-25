# bot/filters/dex_consistency.py

from dataclasses import dataclass
from statistics import mean

@dataclass
class DexConsistencyResult:
    ok: bool
    prices: dict
    spread_pct: float
    reason: str = ""


def dex_consistency_guard(
    dex_prices: dict,
    max_spread_pct: float = 0.40,
) -> DexConsistencyResult:
    """
    dex_prices: {"sushi": price, "uni": price, "quick": price}
    """

    if len(dex_prices) < 2:
        return DexConsistencyResult(
            ok=False,
            prices=dex_prices,
            spread_pct=100.0,
            reason="Not enough DEX quotes",
        )

    values = list(dex_prices.values())
    p_max = max(values)
    p_min = min(values)
    p_mid = mean(values)

    spread_pct = (p_max - p_min) / p_mid * 100.0

    if spread_pct > max_spread_pct:
        return DexConsistencyResult(
            ok=False,
            prices=dex_prices,
            spread_pct=spread_pct,
            reason=f"DEX spread {spread_pct:.2f}% > {max_spread_pct:.2f}%",
        )

    return DexConsistencyResult(
        ok=True,
        prices=dex_prices,
        spread_pct=spread_pct,
    )

