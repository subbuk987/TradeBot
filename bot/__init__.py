# bot/__init__.py
"""
Polygon Arbitrage Bot
Production-grade on-chain arbitrage system

Modules:
- config: Configuration and environment
- pairs: Token and DEX registry
- flash_loan: Aave V3 flash loan integration
- quote_engine: Multi-DEX quote aggregation
- arbitrage_scanner: Opportunity detection
- profit_calculator: Profit calculation
- executor: Trade execution
- main: Entry point
"""

__version__ = "2.0.0"
__author__ = "TradeBot"

# Core components
from bot.config import (
    CHAIN_ID,
    PUBLIC_ADDRESS,
    DRY_RUN_MODE,
    SIMULATION_MODE,
)

from bot.pairs import (
    USDC_LEGACY,
    USDC_NATIVE,
    USDT,
    WMATIC,
    WETH,
    DEXES,
    HIGH_VOLUME_PAIRS,
)

__all__ = [
    "CHAIN_ID",
    "PUBLIC_ADDRESS", 
    "DRY_RUN_MODE",
    "SIMULATION_MODE",
    "USDC_LEGACY",
    "USDC_NATIVE",
    "USDT",
    "WMATIC",
    "WETH",
    "DEXES",
    "HIGH_VOLUME_PAIRS",
]