# bot/decision.py
"""
Unified Decision Engine
Evaluates arbitrage opportunities through multiple safety filters

This module is the GATEKEEPER - no trade executes without passing all guards.
"""

from dataclasses import dataclass
from typing import Dict, Optional
from statistics import median

from web3 import Web3

from bot.pairs import SAFE_PAIRS, get_symbol
from bot.filters.oracle_check import oracle_price_guard
from bot.filters.liquidity_check import liquidity_guard
from bot.filters.dex_consistency import dex_consistency_guard
from bot.filters.profit_check import profit_guard
from bot.gas import estimate_gas_cost_usd


@dataclass
class Decision:
    """Decision result from the evaluation engine"""
    allowed: bool
    reason: str
    details: dict
    
    def __str__(self) -> str:
        status = "✅ ALLOWED" if self.allowed else "❌ REJECTED"
        return f"{status}: {self.reason}"


@dataclass
class TradeEvaluation:
    """Comprehensive trade evaluation"""
    decision: Decision
    oracle_check: Optional[dict] = None
    liquidity_check: Optional[dict] = None
    dex_check: Optional[dict] = None
    profit_check: Optional[dict] = None
    gas_cost_usd: float = 0.0


def evaluate_trade(
    *,
    w3: Web3,
    base_token: str,
    quote_token: str,
    trade_size: float,            # USD value (e.g. 500 USDC)
    dex_prices: Dict[str, float], # {dex: price}
    reserve_in: float,            # base token reserve (human units)
    skip_whitelist: bool = False, # Skip pair whitelist (for testing)
) -> Decision:
    """
    Final unified decision engine
    
    Checks:
    1. Pair whitelist
    2. Oracle price sanity
    3. Liquidity depth
    4. DEX consistency
    5. Profitability after all fees
    
    Returns:
        Decision(allowed=True|False, reason, details)
    """

    # =========================================================
    # 1️⃣ Pair whitelist
    # =========================================================
    if not skip_whitelist and (base_token, quote_token) not in SAFE_PAIRS:
        return Decision(
            allowed=False,
            reason=f"Pair {get_symbol(base_token)}/{get_symbol(quote_token)} not whitelisted",
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
        max_deviation_pct=5.0,  # Allow 5% deviation for volatile pairs
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
        max_impact_pct=1.0,  # Allow 1% impact for smaller trades
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
    dex_check = dex_consistency_guard(
        dex_prices,
        max_spread_pct=3.0,  # Allow 3% spread (looking for bigger gaps)
    )

    if not dex_check.ok:
        return Decision(
            allowed=False,
            reason=f"DEX consistency failed: {dex_check.reason}",
            details=dex_check.__dict__,
        )

    # =========================================================
    # 5️⃣ PROFIT & GAS GUARD
    # =========================================================
    buy_price = min(dex_prices.values())
    sell_price = max(dex_prices.values())

    # Get current gas price
    try:
        gas_price_gwei = w3.eth.gas_price / 10**9
    except Exception:
        gas_price_gwei = 50  # Default
    
    # Get MATIC price (approximate)
    matic_price_usd = 0.50  # Conservative estimate
    
    gas_cost_usd = estimate_gas_cost_usd(
        w3=w3,
        gas_price_gwei=gas_price_gwei,
        matic_price_usd=matic_price_usd,
        include_approval=False,
    )

    profit = profit_guard(
        trade_size_usd=trade_size,
        buy_price=buy_price,
        sell_price=sell_price,
        gas_cost_usd=gas_cost_usd,
        min_profit_usd=0.05,  # Lower threshold for small trades
        min_profit_pct=0.10,  # 0.10% minimum
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
            "gas_cost_usd": gas_cost_usd,
        },
    )


def quick_evaluate(
    dex_prices: Dict[str, float],
    trade_size: float,
    gas_cost_usd: float = 0.05,
) -> tuple:
    """
    Quick evaluation without full checks
    Returns (is_profitable, profit_bps, reason)
    """
    if len(dex_prices) < 2:
        return False, 0, "Need at least 2 DEX quotes"
    
    buy_price = min(dex_prices.values())
    sell_price = max(dex_prices.values())
    
    # Quick profit calculation
    gross_return = trade_size * (sell_price / buy_price)
    dex_fees = trade_size * 0.006  # 0.3% × 2
    gross_profit = gross_return - trade_size - dex_fees
    net_profit = gross_profit - gas_cost_usd
    
    profit_bps = int((net_profit / trade_size) * 10000)
    
    if net_profit > 0 and profit_bps >= 10:
        return True, profit_bps, f"Net profit: ${net_profit:.4f} ({profit_bps} bps)"
    else:
        return False, profit_bps, f"Not profitable: ${net_profit:.4f}"

