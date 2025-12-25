# bot/profit_calculator.py
"""
Comprehensive Profit Calculator
Calculates exact profit after all fees: gas, DEX fees, flash loan fees, slippage
"""

from web3 import Web3
from decimal import Decimal, getcontext
from dataclasses import dataclass
from typing import Optional, Tuple
import time

from bot.pairs import (
    DEXES, TOKENS, get_decimals, get_symbol, is_stablecoin,
    WMATIC, USDC_LEGACY, USDC_NATIVE
)
from bot.config import (
    AAVE_FLASH_LOAN_FEE_BPS, GAS_LIMIT_SWAP, GAS_LIMIT_FLASH_LOAN,
    GAS_LIMIT_TRIANGULAR, MIN_PROFIT_USD, MIN_PROFIT_BPS
)
from bot.arbitrage_scanner import DirectArbOpportunity, TriangularArbOpportunity

getcontext().prec = 50


# =============================================================================
# CHAINLINK ORACLE INTEGRATION
# =============================================================================

CHAINLINK_ABI = [
    {
        "name": "latestRoundData",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [
            {"name": "roundId", "type": "uint80"},
            {"name": "answer", "type": "int256"},
            {"name": "startedAt", "type": "uint256"},
            {"name": "updatedAt", "type": "uint256"},
            {"name": "answeredInRound", "type": "uint80"},
        ],
    },
    {
        "name": "decimals",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "uint8"}],
    },
]

# Chainlink Price Feeds on Polygon
CHAINLINK_FEEDS = {
    "MATIC": Web3.to_checksum_address("0xAB594600376Ec9fD91F8e885dADF0CE036862dE0"),  # MATIC/USD
    "ETH": Web3.to_checksum_address("0xF9680D99D6C9589e2a93a78A04A279e509205945"),    # ETH/USD
    "BTC": Web3.to_checksum_address("0xc907E116054Ad103354f2D350FD2514433D57F6f"),    # BTC/USD
    "LINK": Web3.to_checksum_address("0xd9FFdb71EbE7496cC440152d43986Aae0AB76665"),   # LINK/USD
    "USDC": Web3.to_checksum_address("0xfE4A8cc5b5B2366C1B58Bea3858e81843581b2F7"),   # USDC/USD
    "USDT": Web3.to_checksum_address("0x0A6513e40db6EB1b165753AD52E80663aeA50545"),   # USDT/USD
    "DAI": Web3.to_checksum_address("0x4746DeC9e833A82EC7C2C1356372CcF2cfcD2F3D"),    # DAI/USD
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class GasCost:
    """Gas cost breakdown"""
    gas_units: int
    gas_price_gwei: Decimal
    gas_cost_matic: Decimal
    gas_cost_usd: Decimal
    matic_price_usd: Decimal


@dataclass
class ProfitBreakdown:
    """Complete profit breakdown after all costs"""
    # Input
    trade_amount: Decimal
    trade_amount_usd: Decimal
    
    # Gross profit (before any fees)
    gross_return: Decimal
    gross_profit: Decimal
    gross_profit_bps: int
    
    # Costs
    dex_fee_total: Decimal
    flash_loan_fee: Decimal
    gas_cost: GasCost
    slippage_estimate: Decimal
    
    # Net profit
    total_costs: Decimal
    total_costs_usd: Decimal
    net_profit: Decimal
    net_profit_usd: Decimal
    net_profit_bps: int
    
    # Decision
    is_profitable: bool
    reason: str = ""
    
    # Timing
    calculated_at: float = 0


# =============================================================================
# PROFIT CALCULATOR
# =============================================================================

class ProfitCalculator:
    """
    Calculates exact profitability after all fees and costs
    """
    
    def __init__(self, w3: Web3):
        self.w3 = w3
        self._price_cache = {}
        self._price_cache_ttl = 10  # Cache prices for 10 seconds
    
    def get_matic_price_usd(self) -> Decimal:
        """Get current MATIC price in USD from Chainlink"""
        return self._get_chainlink_price("MATIC")
    
    def get_eth_price_usd(self) -> Decimal:
        """Get current ETH price in USD from Chainlink"""
        return self._get_chainlink_price("ETH")
    
    def _get_chainlink_price(self, symbol: str) -> Decimal:
        """Get price from Chainlink oracle with caching"""
        cache_key = f"chainlink_{symbol}"
        now = time.time()
        
        if cache_key in self._price_cache:
            cached_price, cached_time = self._price_cache[cache_key]
            if now - cached_time < self._price_cache_ttl:
                return cached_price
        
        feed_address = CHAINLINK_FEEDS.get(symbol)
        if not feed_address:
            # Return reasonable defaults
            defaults = {"MATIC": Decimal("0.50"), "ETH": Decimal("2000"), "BTC": Decimal("40000")}
            return defaults.get(symbol, Decimal("1.0"))
        
        try:
            feed = self.w3.eth.contract(address=feed_address, abi=CHAINLINK_ABI)
            _, answer, _, _, _ = feed.functions.latestRoundData().call()
            decimals = feed.functions.decimals().call()
            price = Decimal(answer) / Decimal(10 ** decimals)
            
            self._price_cache[cache_key] = (price, now)
            return price
        except Exception:
            # Return defaults on error
            defaults = {"MATIC": Decimal("0.50"), "ETH": Decimal("2000"), "BTC": Decimal("40000")}
            return defaults.get(symbol, Decimal("1.0"))
    
    def get_token_price_usd(self, token_address: str) -> Decimal:
        """Get USD price for any token"""
        token_address = Web3.to_checksum_address(token_address)
        
        # Map token addresses to Chainlink symbols
        from bot.pairs import WMATIC, WETH, WBTC, LINK, USDC_LEGACY, USDC_NATIVE, USDT, DAI
        
        price_map = {
            WMATIC: "MATIC",
            WETH: "ETH",
            WBTC: "BTC",
            LINK: "LINK",
            USDC_LEGACY: "USDC",
            USDC_NATIVE: "USDC",
            USDT: "USDT",
            DAI: "DAI",
        }
        
        symbol = price_map.get(token_address)
        if symbol:
            return self._get_chainlink_price(symbol)
        
        # For unknown tokens, return 0 (unsafe to trade)
        return Decimal("0")
    
    def estimate_gas_cost(
        self,
        gas_units: int,
        gas_price_gwei: Decimal = None,
    ) -> GasCost:
        """Estimate gas cost in MATIC and USD"""
        if gas_price_gwei is None:
            # Get current gas price from network
            try:
                gas_price_wei = self.w3.eth.gas_price
                gas_price_gwei = Decimal(gas_price_wei) / Decimal(10 ** 9)
            except Exception:
                gas_price_gwei = Decimal("50")  # Default to 50 gwei
        
        gas_cost_matic = Decimal(gas_units) * gas_price_gwei / Decimal(10 ** 9)
        matic_price = self.get_matic_price_usd()
        gas_cost_usd = gas_cost_matic * matic_price
        
        return GasCost(
            gas_units=gas_units,
            gas_price_gwei=gas_price_gwei,
            gas_cost_matic=gas_cost_matic,
            gas_cost_usd=gas_cost_usd,
            matic_price_usd=matic_price,
        )
    
    def calculate_direct_arb_profit(
        self,
        opportunity: DirectArbOpportunity,
        use_flash_loan: bool = True,
        flash_loan_fee_bps: int = AAVE_FLASH_LOAN_FEE_BPS,
        slippage_bps: int = 30,
        gas_price_gwei: Decimal = None,
    ) -> ProfitBreakdown:
        """
        Calculate exact profit for a direct arbitrage opportunity
        """
        now = time.time()
        
        # Get token price for USD conversion
        token_a_price_usd = self.get_token_price_usd(opportunity.token_a)
        trade_amount_usd = opportunity.amount_in * token_a_price_usd
        
        # Gross profit calculation
        gross_return = opportunity.sell_amount_out
        gross_profit = gross_return - opportunity.amount_in
        gross_profit_bps = int((gross_profit / opportunity.amount_in) * 10000) if opportunity.amount_in > 0 else 0
        
        # DEX fees (already accounted for in quotes, but let's be explicit)
        buy_dex_info = DEXES.get(opportunity.buy_dex)
        sell_dex_info = DEXES.get(opportunity.sell_dex)
        
        buy_fee_bps = buy_dex_info.fee_bps if buy_dex_info else 30
        sell_fee_bps = sell_dex_info.fee_bps if sell_dex_info else 30
        
        # DEX fees are already deducted in the quote amounts
        # But we track them for reporting
        dex_fee_total = opportunity.amount_in * Decimal(buy_fee_bps + sell_fee_bps) / Decimal(10000)
        
        # Flash loan fee
        flash_loan_fee = Decimal(0)
        if use_flash_loan:
            flash_loan_fee = opportunity.amount_in * Decimal(flash_loan_fee_bps) / Decimal(10000)
        
        # Gas cost
        gas_units = GAS_LIMIT_FLASH_LOAN if use_flash_loan else GAS_LIMIT_SWAP * 2
        gas_cost = self.estimate_gas_cost(gas_units, gas_price_gwei)
        
        # Convert gas to token terms (approximate)
        gas_cost_in_token = gas_cost.gas_cost_usd / token_a_price_usd if token_a_price_usd > 0 else Decimal(0)
        
        # Slippage estimate
        slippage_estimate = opportunity.amount_in * Decimal(slippage_bps) / Decimal(10000)
        
        # Total costs
        total_costs = flash_loan_fee + gas_cost_in_token + slippage_estimate
        total_costs_usd = total_costs * token_a_price_usd
        
        # Net profit
        net_profit = gross_profit - total_costs
        net_profit_usd = net_profit * token_a_price_usd
        net_profit_bps = int((net_profit / opportunity.amount_in) * 10000) if opportunity.amount_in > 0 else 0
        
        # Decision
        is_profitable = (
            net_profit_usd >= MIN_PROFIT_USD and
            net_profit_bps >= MIN_PROFIT_BPS
        )
        
        reason = ""
        if not is_profitable:
            if net_profit_usd < MIN_PROFIT_USD:
                reason = f"Net profit ${net_profit_usd:.4f} < min ${MIN_PROFIT_USD}"
            elif net_profit_bps < MIN_PROFIT_BPS:
                reason = f"Net profit {net_profit_bps}bps < min {MIN_PROFIT_BPS}bps"
        
        return ProfitBreakdown(
            trade_amount=opportunity.amount_in,
            trade_amount_usd=trade_amount_usd,
            gross_return=gross_return,
            gross_profit=gross_profit,
            gross_profit_bps=gross_profit_bps,
            dex_fee_total=dex_fee_total,
            flash_loan_fee=flash_loan_fee,
            gas_cost=gas_cost,
            slippage_estimate=slippage_estimate,
            total_costs=total_costs,
            total_costs_usd=total_costs_usd,
            net_profit=net_profit,
            net_profit_usd=net_profit_usd,
            net_profit_bps=net_profit_bps,
            is_profitable=is_profitable,
            reason=reason,
            calculated_at=now,
        )
    
    def calculate_triangular_arb_profit(
        self,
        opportunity: TriangularArbOpportunity,
        use_flash_loan: bool = True,
        flash_loan_fee_bps: int = AAVE_FLASH_LOAN_FEE_BPS,
        slippage_bps: int = 50,  # Higher for triangular
        gas_price_gwei: Decimal = None,
    ) -> ProfitBreakdown:
        """
        Calculate exact profit for a triangular arbitrage opportunity
        """
        now = time.time()
        
        # Get token price for USD conversion
        token_a_price_usd = self.get_token_price_usd(opportunity.token_a)
        trade_amount_usd = opportunity.amount_in * token_a_price_usd
        
        # Gross profit
        gross_return = opportunity.final_amount
        gross_profit = gross_return - opportunity.amount_in
        gross_profit_bps = int((gross_profit / opportunity.amount_in) * 10000) if opportunity.amount_in > 0 else 0
        
        # DEX fees (3 hops)
        leg1_fee_bps = DEXES.get(opportunity.leg1_dex, DEXES["quickswap"]).fee_bps
        leg2_fee_bps = DEXES.get(opportunity.leg2_dex, DEXES["quickswap"]).fee_bps
        leg3_fee_bps = DEXES.get(opportunity.leg3_dex, DEXES["quickswap"]).fee_bps
        total_fee_bps = leg1_fee_bps + leg2_fee_bps + leg3_fee_bps
        
        dex_fee_total = opportunity.amount_in * Decimal(total_fee_bps) / Decimal(10000)
        
        # Flash loan fee
        flash_loan_fee = Decimal(0)
        if use_flash_loan:
            flash_loan_fee = opportunity.amount_in * Decimal(flash_loan_fee_bps) / Decimal(10000)
        
        # Gas cost (higher for triangular)
        gas_units = GAS_LIMIT_TRIANGULAR if use_flash_loan else GAS_LIMIT_SWAP * 3
        gas_cost = self.estimate_gas_cost(gas_units, gas_price_gwei)
        
        gas_cost_in_token = gas_cost.gas_cost_usd / token_a_price_usd if token_a_price_usd > 0 else Decimal(0)
        
        # Slippage (higher for 3 hops)
        slippage_estimate = opportunity.amount_in * Decimal(slippage_bps) / Decimal(10000)
        
        # Total costs
        total_costs = flash_loan_fee + gas_cost_in_token + slippage_estimate
        total_costs_usd = total_costs * token_a_price_usd
        
        # Net profit
        net_profit = gross_profit - total_costs
        net_profit_usd = net_profit * token_a_price_usd
        net_profit_bps = int((net_profit / opportunity.amount_in) * 10000) if opportunity.amount_in > 0 else 0
        
        # Decision
        is_profitable = (
            net_profit_usd >= MIN_PROFIT_USD and
            net_profit_bps >= MIN_PROFIT_BPS
        )
        
        reason = ""
        if not is_profitable:
            if net_profit_usd < MIN_PROFIT_USD:
                reason = f"Net profit ${net_profit_usd:.4f} < min ${MIN_PROFIT_USD}"
            elif net_profit_bps < MIN_PROFIT_BPS:
                reason = f"Net profit {net_profit_bps}bps < min {MIN_PROFIT_BPS}bps"
        
        return ProfitBreakdown(
            trade_amount=opportunity.amount_in,
            trade_amount_usd=trade_amount_usd,
            gross_return=gross_return,
            gross_profit=gross_profit,
            gross_profit_bps=gross_profit_bps,
            dex_fee_total=dex_fee_total,
            flash_loan_fee=flash_loan_fee,
            gas_cost=gas_cost,
            slippage_estimate=slippage_estimate,
            total_costs=total_costs,
            total_costs_usd=total_costs_usd,
            net_profit=net_profit,
            net_profit_usd=net_profit_usd,
            net_profit_bps=net_profit_bps,
            is_profitable=is_profitable,
            reason=reason,
            calculated_at=now,
        )
    
    def find_optimal_trade_size(
        self,
        token_a: str,
        token_b: str,
        buy_dex: str,
        sell_dex: str,
        min_amount: Decimal,
        max_amount: Decimal,
        steps: int = 10,
    ) -> Tuple[Decimal, ProfitBreakdown]:
        """
        Find optimal trade size that maximizes profit
        Uses binary search approach
        """
        from bot.arbitrage_scanner import ArbitrageScanner
        scanner = ArbitrageScanner(self.w3)
        
        best_amount = min_amount
        best_breakdown = None
        best_net_profit = Decimal("-inf")
        
        step_size = (max_amount - min_amount) / Decimal(steps)
        
        for i in range(steps + 1):
            amount = min_amount + step_size * Decimal(i)
            
            # Scan for opportunity at this size
            opp = scanner.scan_direct_arbitrage(token_a, token_b, amount)
            
            if not opp:
                continue
            
            # Calculate profit
            breakdown = self.calculate_direct_arb_profit(opp)
            
            if breakdown.net_profit > best_net_profit:
                best_net_profit = breakdown.net_profit
                best_amount = amount
                best_breakdown = breakdown
        
        return best_amount, best_breakdown


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def format_profit_breakdown(breakdown: ProfitBreakdown) -> str:
    """Format profit breakdown for logging"""
    return (
        f"=== Profit Breakdown ===\n"
        f"Trade Amount: {breakdown.trade_amount:.6f} (${breakdown.trade_amount_usd:.2f})\n"
        f"Gross Return: {breakdown.gross_return:.6f}\n"
        f"Gross Profit: {breakdown.gross_profit:.6f} ({breakdown.gross_profit_bps} bps)\n"
        f"--- Costs ---\n"
        f"DEX Fees: {breakdown.dex_fee_total:.6f}\n"
        f"Flash Loan Fee: {breakdown.flash_loan_fee:.6f}\n"
        f"Gas Cost: {breakdown.gas_cost.gas_cost_usd:.4f} USD "
        f"({breakdown.gas_cost.gas_units} gas @ {breakdown.gas_cost.gas_price_gwei:.1f} gwei)\n"
        f"Slippage Est: {breakdown.slippage_estimate:.6f}\n"
        f"Total Costs: {breakdown.total_costs:.6f} (${breakdown.total_costs_usd:.4f})\n"
        f"--- Result ---\n"
        f"Net Profit: {breakdown.net_profit:.6f} (${breakdown.net_profit_usd:.4f})\n"
        f"Net Profit: {breakdown.net_profit_bps} bps\n"
        f"Profitable: {'✅ YES' if breakdown.is_profitable else '❌ NO'}\n"
        f"{f'Reason: {breakdown.reason}' if breakdown.reason else ''}"
    )
