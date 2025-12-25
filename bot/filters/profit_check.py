# bot/filters/profit_check.py

from dataclasses import dataclass


@dataclass
class ProfitResult:
    ok: bool
    gross_profit_usd: float
    gas_cost_usd: float
    net_profit_usd: float
    net_profit_pct: float
    reason: str = ""


def profit_guard(
    *,
    trade_size_usd: float,
    buy_price: float,
    sell_price: float,
    gas_cost_usd: float,
    dex_fee_pct: float = 0.30,
    min_profit_usd: float = 0.20,
    min_profit_pct: float = 0.15,
) -> ProfitResult:
    """
    buy_price  = quote/base (what you pay)
    sell_price = quote/base (what you receive)
    """

    # Gross return before fees
    gross_return = trade_size_usd * (sell_price / buy_price)

    # DEX fees (two swaps worst-case)
    fee_cost = trade_size_usd * (dex_fee_pct / 100) * 2

    gross_profit = gross_return - trade_size_usd - fee_cost

    net_profit = gross_profit - gas_cost_usd
    net_profit_pct = (net_profit / trade_size_usd) * 100

    if net_profit < min_profit_usd:
        return ProfitResult(
            ok=False,
            gross_profit_usd=gross_profit,
            gas_cost_usd=gas_cost_usd,
            net_profit_usd=net_profit,
            net_profit_pct=net_profit_pct,
            reason=f"Net profit ${net_profit:.2f} < ${min_profit_usd:.2f}",
        )

    if net_profit_pct < min_profit_pct:
        return ProfitResult(
            ok=False,
            gross_profit_usd=gross_profit,
            gas_cost_usd=gas_cost_usd,
            net_profit_usd=net_profit,
            net_profit_pct=net_profit_pct,
            reason=f"Net profit {net_profit_pct:.2f}% < {min_profit_pct:.2f}%",
        )

    return ProfitResult(
        ok=True,
        gross_profit_usd=gross_profit,
        gas_cost_usd=gas_cost_usd,
        net_profit_usd=net_profit,
        net_profit_pct=net_profit_pct,
    )

