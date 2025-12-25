# bot/main.py
"""
Production-Grade Arbitrage Bot Main Loop
Target: $4.50 → $150 in 10 days

THIS IS THE ENTRY POINT - Run with: python -m bot.main

MODES:
1. SCAN_ONLY: Just observe opportunities (safe)
2. SIMULATE: Scan + simulate execution (safe)
3. EXECUTE: Real trading (requires DRY_RUN_MODE=False)
"""

import sys
import time
import logging
import signal
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional
from pathlib import Path

from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

from bot.config import (
    RPC_WS_PRIMARY, PUBLIC_ADDRESS, CHAIN_ID,
    INITIAL_CAPITAL_USD, TARGET_CAPITAL_USD, TARGET_DAYS,
    SCAN_INTERVAL_SECONDS, DRY_RUN_MODE, SIMULATION_MODE,
    MIN_PROFIT_USD, MIN_PROFIT_BPS, MAX_GAS_PRICE_GWEI,
    MAX_CONSECUTIVE_FAILURES,
)
from bot.pairs import (
    USDC_LEGACY, USDC_NATIVE, USDT, WMATIC, WETH, DAI,
    HIGH_VOLUME_PAIRS, TRIANGULAR_ROUTES, get_symbol,
)
from bot.rpc_health import RPCHealth
from bot.arbitrage_scanner import ArbitrageScanner, FastArbitrageScanner
from bot.profit_calculator import ProfitCalculator, format_profit_breakdown
from bot.executor import ExecutionEngine, SafeExecutor, ExecutionStatus

# =============================================================================
# LOGGING SETUP
# =============================================================================

LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / f"bot_{datetime.now().strftime('%Y%m%d')}.log"),
    ]
)
logger = logging.getLogger(__name__)


# =============================================================================
# STATISTICS TRACKER
# =============================================================================

class StatisticsTracker:
    """Track bot performance statistics"""
    
    def __init__(self):
        self.start_time = datetime.now()
        self.scan_count = 0
        self.opportunities_found = 0
        self.profitable_opportunities = 0
        self.trades_executed = 0
        self.trades_successful = 0
        self.total_profit_usd = Decimal(0)
        self.total_gas_spent_usd = Decimal(0)
        self.consecutive_failures = 0
        self.best_opportunity_bps = 0
        
    def record_scan(self, opportunities: int, profitable: int):
        self.scan_count += 1
        self.opportunities_found += opportunities
        self.profitable_opportunities += profitable
        
    def record_trade(self, success: bool, profit_usd: Decimal = Decimal(0), gas_usd: Decimal = Decimal(0)):
        self.trades_executed += 1
        if success:
            self.trades_successful += 1
            self.total_profit_usd += profit_usd
            self.consecutive_failures = 0
        else:
            self.consecutive_failures += 1
        self.total_gas_spent_usd += gas_usd
        
    def get_summary(self) -> str:
        runtime = datetime.now() - self.start_time
        success_rate = (self.trades_successful / self.trades_executed * 100) if self.trades_executed > 0 else 0
        
        return (
            f"\n{'='*60}\n"
            f"📊 BOT STATISTICS\n"
            f"{'='*60}\n"
            f"Runtime: {runtime}\n"
            f"Scans: {self.scan_count}\n"
            f"Opportunities Found: {self.opportunities_found}\n"
            f"Profitable (after fees): {self.profitable_opportunities}\n"
            f"Trades Executed: {self.trades_executed}\n"
            f"Trades Successful: {self.trades_successful} ({success_rate:.1f}%)\n"
            f"Total Profit: ${self.total_profit_usd:.4f}\n"
            f"Total Gas Spent: ${self.total_gas_spent_usd:.4f}\n"
            f"Net P&L: ${self.total_profit_usd - self.total_gas_spent_usd:.4f}\n"
            f"Best Opportunity: {self.best_opportunity_bps} bps\n"
            f"{'='*60}\n"
        )


# =============================================================================
# BOT MODES
# =============================================================================

class BotMode:
    SCAN_ONLY = "scan_only"      # Just observe, no execution
    SIMULATE = "simulate"        # Observe + simulate trades
    EXECUTE = "execute"          # Real execution (requires DRY_RUN_MODE=False)


# =============================================================================
# MAIN BOT CLASS
# =============================================================================

class ArbitrageBot:
    """
    Production-grade arbitrage bot for Polygon
    
    Strategy:
    1. Continuous scanning for arbitrage opportunities
    2. Profit validation with all fees included
    3. Safe execution with simulation first
    4. Capital preservation as top priority
    """
    
    def __init__(
        self,
        mode: str = BotMode.SCAN_ONLY,
        trade_size_usd: Decimal = Decimal("4.00"),  # Start with $4 trades
    ):
        self.mode = mode
        self.trade_size = trade_size_usd
        self.running = False
        self.stats = StatisticsTracker()
        
        # Initialize Web3
        logger.info(f"Connecting to RPC: {RPC_WS_PRIMARY}")
        self.w3 = Web3(Web3.HTTPProvider(RPC_WS_PRIMARY))
        self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        
        if not self.w3.is_connected():
            raise RuntimeError("Failed to connect to RPC")
        
        logger.info(f"✅ Connected to Polygon (Chain ID: {self.w3.eth.chain_id})")
        
        # Initialize components
        self.scanner = ArbitrageScanner(self.w3, min_profit_bps=5)  # Low threshold for scanning
        self.fast_scanner = FastArbitrageScanner(self.w3, min_profit_bps=5)
        self.profit_calc = ProfitCalculator(self.w3)
        self.executor = SafeExecutor(self.w3)
        
        # Signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)
    
    def _handle_shutdown(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info("\n🛑 Shutdown signal received...")
        self.running = False
    
    def check_prerequisites(self) -> bool:
        """Check all prerequisites before starting"""
        logger.info("Checking prerequisites...")
        
        # 1. RPC Health
        try:
            rpc = RPCHealth(RPC_WS_PRIMARY)
            ok, status = rpc.check()
            if not ok:
                logger.error(f"❌ RPC unhealthy: {status}")
                return False
            logger.info(f"✅ RPC healthy: {status}")
        except Exception as e:
            logger.error(f"❌ RPC check failed: {e}")
            return False
        
        # 2. Check wallet balance
        try:
            # Check MATIC for gas
            matic_balance = self.w3.eth.get_balance(PUBLIC_ADDRESS)
            matic_human = Decimal(matic_balance) / Decimal(10**18)
            logger.info(f"MATIC balance: {matic_human:.4f}")
            
            if matic_human < Decimal("0.1"):
                logger.warning("⚠️ Low MATIC balance for gas!")
            
            # Check USDC balance
            usdc_balance = self.executor.engine.check_balance(USDC_NATIVE)
            logger.info(f"USDC (native) balance: {usdc_balance:.4f}")
            
            usdc_legacy_balance = self.executor.engine.check_balance(USDC_LEGACY)
            logger.info(f"USDC (legacy) balance: {usdc_legacy_balance:.4f}")
            
            total_usdc = usdc_balance + usdc_legacy_balance
            if total_usdc < self.trade_size:
                logger.warning(f"⚠️ USDC balance ${total_usdc} < trade size ${self.trade_size}")
                
        except Exception as e:
            logger.error(f"❌ Balance check failed: {e}")
            return False
        
        # 3. Check gas prices
        try:
            gas_price = self.w3.eth.gas_price
            gas_gwei = gas_price / 10**9
            logger.info(f"Current gas price: {gas_gwei:.1f} gwei")
            
            if gas_gwei > MAX_GAS_PRICE_GWEI:
                logger.warning(f"⚠️ Gas price {gas_gwei} > max {MAX_GAS_PRICE_GWEI}")
                
        except Exception as e:
            logger.warning(f"⚠️ Gas price check failed: {e}")
        
        logger.info("✅ All prerequisites checked")
        return True
    
    def scan_opportunities(self) -> dict:
        """
        Scan for arbitrage opportunities
        Returns dict with direct and triangular opportunities
        """
        results = {
            "direct": [],
            "triangular": [],
            "best_direct": None,
            "best_triangular": None,
            "scan_time_ms": 0,
        }
        
        start = time.time()
        
        try:
            # Scan direct arbitrage
            scan_result = self.scanner.full_scan(
                amount_in=self.trade_size,
                include_direct=True,
                include_triangular=True,
            )
            
            results["direct"] = scan_result.direct_opportunities
            results["triangular"] = scan_result.triangular_opportunities
            results["best_direct"] = scan_result.best_direct
            results["best_triangular"] = scan_result.best_triangular
            results["scan_time_ms"] = (time.time() - start) * 1000
            
        except Exception as e:
            logger.error(f"Scan error: {e}")
        
        return results
    
    def evaluate_opportunity(self, opportunity) -> Optional[dict]:
        """
        Evaluate an opportunity for profitability
        Returns profit breakdown if profitable, None otherwise
        """
        try:
            from bot.arbitrage_scanner import DirectArbOpportunity, TriangularArbOpportunity
            
            if isinstance(opportunity, DirectArbOpportunity):
                breakdown = self.profit_calc.calculate_direct_arb_profit(
                    opportunity=opportunity,
                    use_flash_loan=False,  # Using own capital
                )
            elif isinstance(opportunity, TriangularArbOpportunity):
                breakdown = self.profit_calc.calculate_triangular_arb_profit(
                    opportunity=opportunity,
                    use_flash_loan=False,
                )
            else:
                return None
            
            return {
                "breakdown": breakdown,
                "is_profitable": breakdown.is_profitable,
                "net_profit_usd": breakdown.net_profit_usd,
                "net_profit_bps": breakdown.net_profit_bps,
            }
            
        except Exception as e:
            logger.error(f"Evaluation error: {e}")
            return None
    
    def execute_opportunity(self, opportunity, breakdown) -> bool:
        """
        Execute a profitable opportunity
        Returns True if successful
        """
        if self.mode == BotMode.SCAN_ONLY:
            logger.info("SCAN_ONLY mode - not executing")
            return False
        
        if self.mode == BotMode.SIMULATE:
            logger.info("SIMULATE mode - would execute here")
            return False
        
        # Real execution
        from bot.arbitrage_scanner import DirectArbOpportunity
        
        if isinstance(opportunity, DirectArbOpportunity):
            result = self.executor.execute_safe_trade(
                opportunity=opportunity,
                profit_breakdown=breakdown,
            )
            
            if result.status == ExecutionStatus.SUCCESS:
                logger.info(f"✅ Trade successful! TX: {result.tx_hash}")
                return True
            else:
                logger.warning(f"❌ Trade failed: {result.error}")
                return False
        
        return False
    
    def run_single_scan(self):
        """Run a single scan cycle"""
        logger.info("-" * 40)
        logger.info(f"Scanning... (Trade size: ${self.trade_size})")
        
        # Scan for opportunities
        scan_results = self.scan_opportunities()
        
        direct_count = len(scan_results["direct"])
        triangular_count = len(scan_results["triangular"])
        
        logger.info(
            f"Found {direct_count} direct, {triangular_count} triangular opportunities "
            f"({scan_results['scan_time_ms']:.0f}ms)"
        )
        
        # Evaluate best direct opportunity
        profitable_count = 0
        
        if scan_results["best_direct"]:
            opp = scan_results["best_direct"]
            evaluation = self.evaluate_opportunity(opp)
            
            if evaluation and evaluation["is_profitable"]:
                profitable_count += 1
                
                logger.info(
                    f"💰 PROFITABLE: {get_symbol(opp.token_a)} ↔ {get_symbol(opp.token_b)}\n"
                    f"   Buy on {opp.buy_dex}, Sell on {opp.sell_dex}\n"
                    f"   Gross: {opp.gross_profit_bps} bps, Net: {evaluation['net_profit_bps']} bps\n"
                    f"   Expected profit: ${evaluation['net_profit_usd']:.4f}"
                )
                
                if evaluation["net_profit_bps"] > self.stats.best_opportunity_bps:
                    self.stats.best_opportunity_bps = evaluation["net_profit_bps"]
                
                # Execute if in execute mode
                if self.mode == BotMode.EXECUTE:
                    success = self.execute_opportunity(opp, evaluation["breakdown"])
                    self.stats.record_trade(
                        success=success,
                        profit_usd=evaluation["net_profit_usd"] if success else Decimal(0),
                    )
            else:
                if opp:
                    logger.debug(
                        f"Best opportunity not profitable after fees: "
                        f"{get_symbol(opp.token_a)} ↔ {get_symbol(opp.token_b)} "
                        f"({opp.gross_profit_bps} bps gross)"
                    )
        
        # Evaluate best triangular
        if scan_results["best_triangular"]:
            opp = scan_results["best_triangular"]
            evaluation = self.evaluate_opportunity(opp)
            
            if evaluation and evaluation["is_profitable"]:
                profitable_count += 1
                
                logger.info(
                    f"💰 TRIANGULAR: {get_symbol(opp.token_a)} → {get_symbol(opp.token_b)} → "
                    f"{get_symbol(opp.token_c)} → {get_symbol(opp.token_a)}\n"
                    f"   Net profit: ${evaluation['net_profit_usd']:.4f} ({evaluation['net_profit_bps']} bps)"
                )
        
        # Update statistics
        self.stats.record_scan(
            opportunities=direct_count + triangular_count,
            profitable=profitable_count,
        )
        
        return profitable_count > 0
    
    def run(self):
        """
        Main bot loop
        Continuously scans and executes opportunities
        """
        logger.info("=" * 60)
        logger.info("🚀 ARBITRAGE BOT STARTING")
        logger.info(f"Mode: {self.mode}")
        logger.info(f"Trade Size: ${self.trade_size}")
        logger.info(f"Target: ${INITIAL_CAPITAL_USD} → ${TARGET_CAPITAL_USD} in {TARGET_DAYS} days")
        logger.info("=" * 60)
        
        # Check prerequisites
        if not self.check_prerequisites():
            logger.error("Prerequisites check failed. Exiting.")
            return
        
        self.running = True
        
        try:
            while self.running:
                try:
                    # Run scan
                    self.run_single_scan()
                    
                    # Check circuit breakers
                    if self.stats.consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                        logger.error(f"❌ Too many consecutive failures ({MAX_CONSECUTIVE_FAILURES}). Pausing...")
                        time.sleep(60)  # Pause for 1 minute
                        self.stats.consecutive_failures = 0
                    
                    # Wait before next scan
                    time.sleep(SCAN_INTERVAL_SECONDS)
                    
                except Exception as e:
                    logger.error(f"Loop error: {e}")
                    time.sleep(5)
                    
        except KeyboardInterrupt:
            logger.info("\nKeyboard interrupt received")
        
        finally:
            logger.info(self.stats.get_summary())
            logger.info("Bot stopped.")


# =============================================================================
# QUICK TEST FUNCTION
# =============================================================================

def quick_test():
    """
    Quick test to verify everything is working
    Runs one scan and shows results
    """
    logger.info("=" * 60)
    logger.info("🧪 QUICK TEST MODE")
    logger.info("=" * 60)
    
    bot = ArbitrageBot(
        mode=BotMode.SCAN_ONLY,
        trade_size_usd=Decimal("100"),  # Test with $100 hypothetical
    )
    
    if not bot.check_prerequisites():
        logger.error("Prerequisites failed")
        return
    
    # Run single scan
    bot.run_single_scan()
    
    logger.info("\n✅ Quick test complete!")
    logger.info(bot.stats.get_summary())


# =============================================================================
# ENTRY POINT
# =============================================================================

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Polygon Arbitrage Bot")
    parser.add_argument(
        "--mode",
        choices=["scan", "simulate", "execute", "test"],
        default="scan",
        help="Bot mode: scan (observe only), simulate, execute (real trades), test (quick test)"
    )
    parser.add_argument(
        "--trade-size",
        type=float,
        default=4.0,
        help="Trade size in USD (default: 4.0)"
    )
    
    args = parser.parse_args()
    
    if args.mode == "test":
        quick_test()
        return
    
    mode_map = {
        "scan": BotMode.SCAN_ONLY,
        "simulate": BotMode.SIMULATE,
        "execute": BotMode.EXECUTE,
    }
    
    bot = ArbitrageBot(
        mode=mode_map[args.mode],
        trade_size_usd=Decimal(str(args.trade_size)),
    )
    
    bot.run()


if __name__ == "__main__":
    main()


