# bot/filters/liquidity_check.py

from dataclasses import dataclass

@dataclass
class LiquidityResult:
    ok: bool
    reserve_in: float
    trade_size: float
    price_impact_pct: float
    reason: str = ""


def liquidity_guard(
    reserve_in: float,
    trade_size: float,
    max_impact_pct: float = 0.30,
) -> LiquidityResult:
    """
    reserve_in: reserve of input token (human units)
    trade_size: trade size of input token (human units)
    """

    if reserve_in <= 0:
        return LiquidityResult(
            ok=False,
            reserve_in=reserve_in,
            trade_size=trade_size,
            price_impact_pct=100.0,
            reason="Zero or invalid liquidity",
        )

    impact_pct = (trade_size / reserve_in) * 100.0

    if impact_pct > max_impact_pct:
        return LiquidityResult(
            ok=False,
            reserve_in=reserve_in,
            trade_size=trade_size,
            price_impact_pct=impact_pct,
            reason=f"Price impact {impact_pct:.2f}% > {max_impact_pct:.2f}%",
        )

    return LiquidityResult(
        ok=True,
        reserve_in=reserve_in,
        trade_size=trade_size,
        price_impact_pct=impact_pct,
    )

