# bot/arbitrage_scanner.py
"""
Advanced Arbitrage Scanner
Detects direct and triangular arbitrage opportunities across multiple DEXs
"""

from web3 import Web3
from decimal import Decimal, getcontext
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import logging

from bot.pairs import (
    DEXES, TOKENS, HIGH_VOLUME_PAIRS, TRIANGULAR_ROUTES,
    USDC_LEGACY, USDC_NATIVE, USDT, WMATIC, WETH, DAI,
    get_decimals, get_symbol, is_stablecoin
)
from bot.quote_engine import QuoteEngine, Quote, AggregatedQuotes

getcontext().prec = 50
logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class DirectArbOpportunity:
    """Direct arbitrage: Buy on DEX A, sell on DEX B"""
    opportunity_id: str
    token_a: str  # Base token (what we start with)
    token_b: str  # Quote token (what we swap to)
    amount_in: Decimal
    
    # Buy leg
    buy_dex: str
    buy_amount_out: Decimal
    buy_price: Decimal
    
    # Sell leg
    sell_dex: str
    sell_amount_out: Decimal
    sell_price: Decimal
    
    # Profit metrics
    gross_profit: Decimal
    gross_profit_bps: int
    
    # Timestamps
    detected_at: float
    expires_at: float  # Opportunities are time-sensitive
    
    def is_expired(self) -> bool:
        return time.time() > self.expires_at


@dataclass
class TriangularArbOpportunity:
    """Triangular arbitrage: A → B → C → A"""
    opportunity_id: str
    token_a: str
    token_b: str
    token_c: str
    amount_in: Decimal
    
    # Leg 1: A → B
    leg1_dex: str
    leg1_amount_out: Decimal
    leg1_price: Decimal
    
    # Leg 2: B → C
    leg2_dex: str
    leg2_amount_out: Decimal
    leg2_price: Decimal
    
    # Leg 3: C → A
    leg3_dex: str
    leg3_amount_out: Decimal
    leg3_price: Decimal
    
    # Profit metrics
    final_amount: Decimal
    gross_profit: Decimal
    gross_profit_bps: int
    
    # Timestamps
    detected_at: float
    expires_at: float
    
    def is_expired(self) -> bool:
        return time.time() > self.expires_at


@dataclass
class ScanResult:
    """Result of an arbitrage scan cycle"""
    timestamp: float
    scan_duration_ms: float
    pairs_scanned: int
    routes_scanned: int
    direct_opportunities: List[DirectArbOpportunity]
    triangular_opportunities: List[TriangularArbOpportunity]
    best_direct: Optional[DirectArbOpportunity] = None
    best_triangular: Optional[TriangularArbOpportunity] = None
    errors: List[str] = field(default_factory=list)


# =============================================================================
# ARBITRAGE SCANNER
# =============================================================================

class ArbitrageScanner:
    """
    Production-grade arbitrage opportunity scanner
    Scans multiple DEXs for direct and triangular arbitrage
    """
    
    def __init__(
        self,
        w3: Web3,
        min_profit_bps: int = 10,  # Minimum 0.10% profit
        opportunity_ttl_seconds: float = 3.0,  # Opportunities expire after 3s
    ):
        self.w3 = w3
        self.quote_engine = QuoteEngine(w3)
        self.min_profit_bps = min_profit_bps
        self.opportunity_ttl = opportunity_ttl_seconds
        self._opportunity_counter = 0
        
    def _generate_opportunity_id(self) -> str:
        """Generate unique opportunity ID"""
        self._opportunity_counter += 1
        return f"ARB-{int(time.time())}-{self._opportunity_counter}"
    
    def scan_direct_arbitrage(
        self,
        token_a: str,
        token_b: str,
        amount_in: Decimal,
        dex_list: List[str] = None,
    ) -> Optional[DirectArbOpportunity]:
        """
        Scan for direct arbitrage opportunity between two tokens
        Buy on cheapest DEX, sell on most expensive DEX
        """
        if dex_list is None:
            dex_list = list(DEXES.keys())
        
        # Get quotes: A → B (buy token B with token A)
        forward_quotes = self.quote_engine.aggregate_quotes(
            token_a, token_b, amount_in, dex_list
        )
        
        if len(forward_quotes.quotes) < 2:
            return None
        
        # For each quote, get the reverse quote
        best_profit = Decimal(0)
        best_opp = None
        
        for buy_dex, buy_quote in forward_quotes.quotes.items():
            if not buy_quote.is_valid:
                continue
            
            # Get reverse quotes: B → A (sell token B for token A)
            for sell_dex, _ in forward_quotes.quotes.items():
                if sell_dex == buy_dex:
                    continue
                
                # Get specific reverse quote
                sell_quote = self.quote_engine.get_quote(
                    sell_dex, token_b, token_a, buy_quote.amount_out
                )
                
                if not sell_quote.is_valid:
                    continue
                
                # Calculate profit
                final_amount = sell_quote.amount_out
                gross_profit = final_amount - amount_in
                
                if gross_profit <= 0:
                    continue
                
                gross_profit_bps = int((gross_profit / amount_in) * 10000)
                
                if gross_profit_bps < self.min_profit_bps:
                    continue
                
                if gross_profit > best_profit:
                    best_profit = gross_profit
                    best_opp = DirectArbOpportunity(
                        opportunity_id=self._generate_opportunity_id(),
                        token_a=token_a,
                        token_b=token_b,
                        amount_in=amount_in,
                        buy_dex=buy_dex,
                        buy_amount_out=buy_quote.amount_out,
                        buy_price=buy_quote.price,
                        sell_dex=sell_dex,
                        sell_amount_out=sell_quote.amount_out,
                        sell_price=sell_quote.price,
                        gross_profit=gross_profit,
                        gross_profit_bps=gross_profit_bps,
                        detected_at=time.time(),
                        expires_at=time.time() + self.opportunity_ttl,
                    )
        
        return best_opp
    
    def scan_triangular_arbitrage(
        self,
        token_a: str,
        token_b: str,
        token_c: str,
        amount_in: Decimal,
        dex_list: List[str] = None,
    ) -> Optional[TriangularArbOpportunity]:
        """
        Scan for triangular arbitrage: A → B → C → A
        Can use same or different DEXs for each leg
        """
        if dex_list is None:
            dex_list = list(DEXES.keys())
        
        best_profit = Decimal(0)
        best_opp = None
        
        # Try all DEX combinations for each leg
        for dex1 in dex_list:
            # Leg 1: A → B
            quote1 = self.quote_engine.get_quote(dex1, token_a, token_b, amount_in)
            if not quote1.is_valid or quote1.amount_out <= 0:
                continue
            
            for dex2 in dex_list:
                # Leg 2: B → C
                quote2 = self.quote_engine.get_quote(
                    dex2, token_b, token_c, quote1.amount_out
                )
                if not quote2.is_valid or quote2.amount_out <= 0:
                    continue
                
                for dex3 in dex_list:
                    # Leg 3: C → A
                    quote3 = self.quote_engine.get_quote(
                        dex3, token_c, token_a, quote2.amount_out
                    )
                    if not quote3.is_valid or quote3.amount_out <= 0:
                        continue
                    
                    # Calculate profit
                    final_amount = quote3.amount_out
                    gross_profit = final_amount - amount_in
                    
                    if gross_profit <= 0:
                        continue
                    
                    gross_profit_bps = int((gross_profit / amount_in) * 10000)
                    
                    if gross_profit_bps < self.min_profit_bps:
                        continue
                    
                    if gross_profit > best_profit:
                        best_profit = gross_profit
                        best_opp = TriangularArbOpportunity(
                            opportunity_id=self._generate_opportunity_id(),
                            token_a=token_a,
                            token_b=token_b,
                            token_c=token_c,
                            amount_in=amount_in,
                            leg1_dex=dex1,
                            leg1_amount_out=quote1.amount_out,
                            leg1_price=quote1.price,
                            leg2_dex=dex2,
                            leg2_amount_out=quote2.amount_out,
                            leg2_price=quote2.price,
                            leg3_dex=dex3,
                            leg3_amount_out=quote3.amount_out,
                            leg3_price=quote3.price,
                            final_amount=final_amount,
                            gross_profit=gross_profit,
                            gross_profit_bps=gross_profit_bps,
                            detected_at=time.time(),
                            expires_at=time.time() + self.opportunity_ttl,
                        )
        
        return best_opp
    
    def scan_all_pairs(
        self,
        amount_in: Decimal,
        pairs: List[Tuple[str, str]] = None,
    ) -> List[DirectArbOpportunity]:
        """
        Scan all configured pairs for direct arbitrage
        """
        if pairs is None:
            pairs = HIGH_VOLUME_PAIRS
        
        opportunities = []
        
        for token_a, token_b in pairs:
            try:
                opp = self.scan_direct_arbitrage(token_a, token_b, amount_in)
                if opp:
                    opportunities.append(opp)
            except Exception as e:
                logger.warning(f"Error scanning {get_symbol(token_a)}/{get_symbol(token_b)}: {e}")
        
        return sorted(opportunities, key=lambda x: x.gross_profit_bps, reverse=True)
    
    def scan_all_triangular(
        self,
        amount_in: Decimal,
        routes: List[Tuple[str, str, str]] = None,
    ) -> List[TriangularArbOpportunity]:
        """
        Scan all configured triangular routes
        """
        if routes is None:
            routes = TRIANGULAR_ROUTES
        
        opportunities = []
        
        for token_a, token_b, token_c in routes:
            try:
                opp = self.scan_triangular_arbitrage(
                    token_a, token_b, token_c, amount_in
                )
                if opp:
                    opportunities.append(opp)
            except Exception as e:
                logger.warning(
                    f"Error scanning triangular "
                    f"{get_symbol(token_a)}/{get_symbol(token_b)}/{get_symbol(token_c)}: {e}"
                )
        
        return sorted(opportunities, key=lambda x: x.gross_profit_bps, reverse=True)
    
    def full_scan(
        self,
        amount_in: Decimal,
        include_direct: bool = True,
        include_triangular: bool = True,
    ) -> ScanResult:
        """
        Perform full arbitrage scan across all pairs and routes
        """
        start_time = time.time()
        errors = []
        
        direct_opps = []
        triangular_opps = []
        pairs_scanned = 0
        routes_scanned = 0
        
        if include_direct:
            try:
                direct_opps = self.scan_all_pairs(amount_in)
                pairs_scanned = len(HIGH_VOLUME_PAIRS)
            except Exception as e:
                errors.append(f"Direct scan error: {e}")
        
        if include_triangular:
            try:
                triangular_opps = self.scan_all_triangular(amount_in)
                routes_scanned = len(TRIANGULAR_ROUTES)
            except Exception as e:
                errors.append(f"Triangular scan error: {e}")
        
        scan_duration_ms = (time.time() - start_time) * 1000
        
        return ScanResult(
            timestamp=start_time,
            scan_duration_ms=scan_duration_ms,
            pairs_scanned=pairs_scanned,
            routes_scanned=routes_scanned,
            direct_opportunities=direct_opps,
            triangular_opportunities=triangular_opps,
            best_direct=direct_opps[0] if direct_opps else None,
            best_triangular=triangular_opps[0] if triangular_opps else None,
            errors=errors,
        )


# =============================================================================
# OPTIMIZED SCANNER FOR HIGH-FREQUENCY SCANNING
# =============================================================================

class FastArbitrageScanner:
    """
    Optimized scanner for sub-second opportunity detection
    Uses caching and parallel execution for speed
    """
    
    def __init__(
        self,
        w3: Web3,
        min_profit_bps: int = 10,
        max_workers: int = 4,
    ):
        self.w3 = w3
        self.quote_engine = QuoteEngine(w3)
        self.min_profit_bps = min_profit_bps
        self.max_workers = max_workers
        self._opportunity_counter = 0
    
    def _generate_opportunity_id(self) -> str:
        self._opportunity_counter += 1
        return f"FAST-{int(time.time() * 1000)}-{self._opportunity_counter}"
    
    def scan_pair_parallel(
        self,
        pairs_with_amounts: List[Tuple[str, str, Decimal]],
    ) -> List[DirectArbOpportunity]:
        """
        Scan multiple pairs in parallel
        """
        opportunities = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(
                    self._scan_single_pair, token_a, token_b, amount
                ): (token_a, token_b)
                for token_a, token_b, amount in pairs_with_amounts
            }
            
            for future in as_completed(futures):
                try:
                    opp = future.result()
                    if opp:
                        opportunities.append(opp)
                except Exception:
                    pass
        
        return sorted(opportunities, key=lambda x: x.gross_profit_bps, reverse=True)
    
    def _scan_single_pair(
        self,
        token_a: str,
        token_b: str,
        amount_in: Decimal,
    ) -> Optional[DirectArbOpportunity]:
        """
        Quick scan for a single pair
        Only checks best/worst DEX combinations
        """
        # Get aggregated forward quotes
        forward = self.quote_engine.aggregate_quotes(token_a, token_b, amount_in)
        
        if not forward.best_quote or not forward.worst_quote:
            return None
        
        if forward.spread_bps < self.min_profit_bps:
            return None  # Not enough spread to be profitable
        
        # Get reverse quote from best forward DEX
        best_buy = forward.best_quote
        
        # Try selling on the DEX with worst buy price (likely best sell price)
        worst_buy_dex = forward.worst_quote.dex
        
        sell_quote = self.quote_engine.get_quote(
            worst_buy_dex, token_b, token_a, best_buy.amount_out
        )
        
        if not sell_quote.is_valid:
            return None
        
        # Calculate profit
        final_amount = sell_quote.amount_out
        gross_profit = final_amount - amount_in
        
        if gross_profit <= 0:
            return None
        
        gross_profit_bps = int((gross_profit / amount_in) * 10000)
        
        if gross_profit_bps < self.min_profit_bps:
            return None
        
        return DirectArbOpportunity(
            opportunity_id=self._generate_opportunity_id(),
            token_a=token_a,
            token_b=token_b,
            amount_in=amount_in,
            buy_dex=best_buy.dex,
            buy_amount_out=best_buy.amount_out,
            buy_price=best_buy.price,
            sell_dex=sell_quote.dex,
            sell_amount_out=sell_quote.amount_out,
            sell_price=sell_quote.price,
            gross_profit=gross_profit,
            gross_profit_bps=gross_profit_bps,
            detected_at=time.time(),
            expires_at=time.time() + 3.0,
        )


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def format_opportunity(opp: DirectArbOpportunity) -> str:
    """Format opportunity for logging"""
    return (
        f"[{opp.opportunity_id}] "
        f"{get_symbol(opp.token_a)} → {get_symbol(opp.token_b)} → {get_symbol(opp.token_a)}\n"
        f"  Buy on {opp.buy_dex}: {opp.amount_in} → {opp.buy_amount_out:.6f}\n"
        f"  Sell on {opp.sell_dex}: {opp.buy_amount_out:.6f} → {opp.sell_amount_out:.6f}\n"
        f"  Profit: {opp.gross_profit:.6f} ({opp.gross_profit_bps} bps)"
    )


def format_triangular_opportunity(opp: TriangularArbOpportunity) -> str:
    """Format triangular opportunity for logging"""
    return (
        f"[{opp.opportunity_id}] Triangular Arb\n"
        f"  {get_symbol(opp.token_a)} → {get_symbol(opp.token_b)} ({opp.leg1_dex}): "
        f"{opp.amount_in} → {opp.leg1_amount_out:.6f}\n"
        f"  {get_symbol(opp.token_b)} → {get_symbol(opp.token_c)} ({opp.leg2_dex}): "
        f"{opp.leg1_amount_out:.6f} → {opp.leg2_amount_out:.6f}\n"
        f"  {get_symbol(opp.token_c)} → {get_symbol(opp.token_a)} ({opp.leg3_dex}): "
        f"{opp.leg2_amount_out:.6f} → {opp.final_amount:.6f}\n"
        f"  Profit: {opp.gross_profit:.6f} ({opp.gross_profit_bps} bps)"
    )
