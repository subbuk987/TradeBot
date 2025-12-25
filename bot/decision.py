# bot/decision.py

from dataclasses import dataclass
from typing import Dict
from statistics import median

from web3 import Web3

from bot.pairs import SAFE_PAIRS
from bot.filters.oracle_check import oracle_price_guard
from bot.filters.liquidity_check import liquidity_guard
from bot.filters.dex_consistency import dex_consistency_guard
from bot.filters.profit_check import profit_guard
from bot.gas import estimate_gas_cost_usd


@dataclass
class Decision:
    allowed: bool
    reason: str
    details: dict


def evaluate_trade(
    *,
    w3: Web3,
    base_token: str,
    quote_token: str,
    trade_size: float,            # USD value (e.g. 500 USDC)
    dex_prices: Dict[str, float], # {dex: price}
    reserve_in: float,            # base token reserve (human units)
) -> Decision:
    """
    Final unified decision engine (Stages 1–7)

    Returns:
        Decision(allowed=True|False, reason, details)
    """

    # =========================================================
    # 1️⃣ Pair whitelist
    # =========================================================
    if (base_token, quote_token) not in SAFE_PAIRS:
        return Decision(
            allowed=False,
            reason="Pair not whitelisted",
            details={},
        )

    # =========================================================
    # 2️⃣ Oracle price guard
    # =========================================================
    representative_price = median(dex_prices.values())

    oracle = oracle_price_guard(
        w3=w3,
        base_token=base_token,
        quote_token=quote_token,
        quoted_price=representative_price,
    )

    if not oracle.ok:
        return Decision(
            allowed=False,
            reason=f"Oracle guard failed: {oracle.reason}",
            details=oracle.__dict__,
        )

    # =========================================================
    # 3️⃣ Liquidity guard
    # =========================================================
    liquidity = liquidity_guard(
        reserve_in=reserve_in,
        trade_size=trade_size,
    )

    if not liquidity.ok:
        return Decision(
            allowed=False,
            reason=f"Liquidity guard failed: {liquidity.reason}",
            details=liquidity.__dict__,
        )

    # =========================================================
    # 4️⃣ DEX consistency guard
    # =========================================================
    dex_check = dex_consistency_guard(dex_prices)

    if not dex_check.ok:
        return Decision(
            allowed=False,
            reason=f"DEX consistency failed: {dex_check.reason}",
            details=dex_check.__dict__,
        )

    # =========================================================
    # 5️⃣ PROFIT & GAS GUARD (STAGE 7)
    # =========================================================
    buy_price  = min(dex_prices.values())
    sell_price = max(dex_prices.values())

    # Conservative Polygon assumptions
    gas_cost_usd = estimate_gas_cost_usd(
        w3=w3,
        gas_price_gwei=50,        # conservative
        matic_price_usd=0.70,     # conservative
        include_approval=False,   # approval already handled
    )

    profit = profit_guard(
        trade_size_usd=trade_size,
        buy_price=buy_price,
        sell_price=sell_price,
        gas_cost_usd=gas_cost_usd,
    )

    if not profit.ok:
        return Decision(
            allowed=False,
            reason=f"Profit guard failed: {profit.reason}",
            details=profit.__dict__,
        )

    # =========================================================
    # ✅ ALL GUARDS PASSED
    # =========================================================
    return Decision(
        allowed=True,
        reason="All guards passed (profitable)",
        details={
            "oracle": oracle.__dict__,
            "liquidity": liquidity.__dict__,
            "dex": dex_check.__dict__,
            "profit": profit.__dict__,
        },
    )

