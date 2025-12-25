# bot/quote_engine.py
"""
Advanced Multi-DEX Quote Engine with Price Impact Calculation
Fetches real-time quotes from all DEXs and calculates optimal trade routes
"""

from web3 import Web3
from decimal import Decimal, getcontext
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from bot.pairs import (
    DEXES, TOKENS, get_decimals, get_symbol, DexInfo,
    WMATIC, WETH, USDC_LEGACY, USDC_NATIVE, USDT, DAI
)

getcontext().prec = 50

# =============================================================================
# ROUTER ABI (Universal for V2 forks)
# =============================================================================

ROUTER_V2_ABI = [
    {
        "name": "getAmountsOut",
        "type": "function",
        "stateMutability": "view",
        "inputs": [
            {"name": "amountIn", "type": "uint256"},
            {"name": "path", "type": "address[]"},
        ],
        "outputs": [{"name": "amounts", "type": "uint256[]"}],
    },
    {
        "name": "getAmountsIn",
        "type": "function",
        "stateMutability": "view",
        "inputs": [
            {"name": "amountOut", "type": "uint256"},
            {"name": "path", "type": "address[]"},
        ],
        "outputs": [{"name": "amounts", "type": "uint256[]"}],
    },
    {
        "name": "swapExactTokensForTokens",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "amountIn", "type": "uint256"},
            {"name": "amountOutMin", "type": "uint256"},
            {"name": "path", "type": "address[]"},
            {"name": "to", "type": "address"},
            {"name": "deadline", "type": "uint256"},
        ],
        "outputs": [{"name": "amounts", "type": "uint256[]"}],
    },
]

FACTORY_ABI = [
    {
        "name": "getPair",
        "type": "function",
        "stateMutability": "view",
        "inputs": [
            {"name": "tokenA", "type": "address"},
            {"name": "tokenB", "type": "address"},
        ],
        "outputs": [{"name": "pair", "type": "address"}],
    },
]

PAIR_ABI = [
    {
        "name": "getReserves",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [
            {"name": "reserve0", "type": "uint112"},
            {"name": "reserve1", "type": "uint112"},
            {"name": "blockTimestampLast", "type": "uint32"},
        ],
    },
    {
        "name": "token0",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "address"}],
    },
    {
        "name": "token1",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "address"}],
    },
]


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class Quote:
    """Single DEX quote"""
    dex: str
    token_in: str
    token_out: str
    amount_in: Decimal
    amount_out: Decimal
    price: Decimal  # token_out per token_in
    fee_bps: int
    timestamp: float
    is_valid: bool = True
    error: str = ""
    

@dataclass
class PoolReserves:
    """Pool reserve information"""
    dex: str
    token0: str
    token1: str
    reserve0: int
    reserve1: int
    reserve0_human: Decimal
    reserve1_human: Decimal
    

@dataclass  
class AggregatedQuotes:
    """Aggregated quotes from all DEXs"""
    token_in: str
    token_out: str
    amount_in: Decimal
    quotes: Dict[str, Quote] = field(default_factory=dict)
    best_quote: Optional[Quote] = None
    worst_quote: Optional[Quote] = None
    spread_bps: int = 0
    timestamp: float = 0


@dataclass
class ArbitrageOpportunity:
    """Detected arbitrage opportunity"""
    token_in: str
    token_out: str
    amount_in: Decimal
    buy_dex: str
    sell_dex: str
    buy_price: Decimal
    sell_price: Decimal
    expected_out: Decimal
    gross_profit: Decimal
    gross_profit_bps: int
    timestamp: float


# =============================================================================
# QUOTE ENGINE
# =============================================================================

class QuoteEngine:
    """
    Advanced multi-DEX quote aggregation engine
    """
    
    def __init__(self, w3: Web3):
        self.w3 = w3
        self._router_cache: Dict[str, any] = {}
        self._factory_cache: Dict[str, any] = {}
        self._pair_cache: Dict[Tuple[str, str, str], str] = {}
        
    def _get_router(self, dex_name: str):
        """Get cached router contract"""
        if dex_name not in self._router_cache:
            dex_info = DEXES.get(dex_name)
            if not dex_info:
                return None
            self._router_cache[dex_name] = self.w3.eth.contract(
                address=dex_info.router,
                abi=ROUTER_V2_ABI
            )
        return self._router_cache[dex_name]
    
    def _get_factory(self, dex_name: str):
        """Get cached factory contract"""
        if dex_name not in self._factory_cache:
            dex_info = DEXES.get(dex_name)
            if not dex_info:
                return None
            self._factory_cache[dex_name] = self.w3.eth.contract(
                address=dex_info.factory,
                abi=FACTORY_ABI
            )
        return self._factory_cache[dex_name]
    
    def get_pair_address(self, dex_name: str, token_a: str, token_b: str) -> Optional[str]:
        """Get pair address from factory"""
        cache_key = (dex_name, token_a, token_b)
        reverse_key = (dex_name, token_b, token_a)
        
        if cache_key in self._pair_cache:
            return self._pair_cache[cache_key]
        if reverse_key in self._pair_cache:
            return self._pair_cache[reverse_key]
        
        factory = self._get_factory(dex_name)
        if not factory:
            return None
            
        try:
            pair = factory.functions.getPair(
                Web3.to_checksum_address(token_a),
                Web3.to_checksum_address(token_b)
            ).call()
            
            if pair == "0x0000000000000000000000000000000000000000":
                return None
                
            self._pair_cache[cache_key] = pair
            return pair
        except Exception:
            return None
    
    def get_reserves(self, dex_name: str, token_a: str, token_b: str) -> Optional[PoolReserves]:
        """Get pool reserves for a pair"""
        pair_addr = self.get_pair_address(dex_name, token_a, token_b)
        if not pair_addr:
            return None
            
        try:
            pair = self.w3.eth.contract(address=pair_addr, abi=PAIR_ABI)
            r0, r1, _ = pair.functions.getReserves().call()
            t0 = pair.functions.token0().call()
            t1 = pair.functions.token1().call()
            
            dec0 = get_decimals(t0)
            dec1 = get_decimals(t1)
            
            return PoolReserves(
                dex=dex_name,
                token0=t0,
                token1=t1,
                reserve0=r0,
                reserve1=r1,
                reserve0_human=Decimal(r0) / Decimal(10 ** dec0),
                reserve1_human=Decimal(r1) / Decimal(10 ** dec1),
            )
        except Exception:
            return None
    
    def get_quote(
        self,
        dex_name: str,
        token_in: str,
        token_out: str,
        amount_in: Decimal,
    ) -> Quote:
        """Get quote from a single DEX"""
        timestamp = time.time()
        
        router = self._get_router(dex_name)
        if not router:
            return Quote(
                dex=dex_name,
                token_in=token_in,
                token_out=token_out,
                amount_in=amount_in,
                amount_out=Decimal(0),
                price=Decimal(0),
                fee_bps=0,
                timestamp=timestamp,
                is_valid=False,
                error=f"DEX {dex_name} not found"
            )
        
        dex_info = DEXES[dex_name]
        dec_in = get_decimals(token_in)
        dec_out = get_decimals(token_out)
        
        try:
            amount_in_wei = int(amount_in * Decimal(10 ** dec_in))
            path = [
                Web3.to_checksum_address(token_in),
                Web3.to_checksum_address(token_out)
            ]
            
            amounts = router.functions.getAmountsOut(amount_in_wei, path).call()
            amount_out_wei = amounts[-1]
            amount_out = Decimal(amount_out_wei) / Decimal(10 ** dec_out)
            
            # Price = amount_out / amount_in
            price = amount_out / amount_in if amount_in > 0 else Decimal(0)
            
            return Quote(
                dex=dex_name,
                token_in=token_in,
                token_out=token_out,
                amount_in=amount_in,
                amount_out=amount_out,
                price=price,
                fee_bps=dex_info.fee_bps,
                timestamp=timestamp,
                is_valid=True,
            )
            
        except Exception as e:
            return Quote(
                dex=dex_name,
                token_in=token_in,
                token_out=token_out,
                amount_in=amount_in,
                amount_out=Decimal(0),
                price=Decimal(0),
                fee_bps=dex_info.fee_bps,
                timestamp=timestamp,
                is_valid=False,
                error=str(e)
            )
    
    def get_multi_hop_quote(
        self,
        dex_name: str,
        path: List[str],
        amount_in: Decimal,
    ) -> Quote:
        """Get quote for multi-hop swap (e.g., A -> B -> C)"""
        timestamp = time.time()
        
        router = self._get_router(dex_name)
        if not router:
            return Quote(
                dex=dex_name,
                token_in=path[0],
                token_out=path[-1],
                amount_in=amount_in,
                amount_out=Decimal(0),
                price=Decimal(0),
                fee_bps=0,
                timestamp=timestamp,
                is_valid=False,
                error=f"DEX {dex_name} not found"
            )
        
        dex_info = DEXES[dex_name]
        dec_in = get_decimals(path[0])
        dec_out = get_decimals(path[-1])
        
        try:
            amount_in_wei = int(amount_in * Decimal(10 ** dec_in))
            checksum_path = [Web3.to_checksum_address(t) for t in path]
            
            amounts = router.functions.getAmountsOut(amount_in_wei, checksum_path).call()
            amount_out_wei = amounts[-1]
            amount_out = Decimal(amount_out_wei) / Decimal(10 ** dec_out)
            
            price = amount_out / amount_in if amount_in > 0 else Decimal(0)
            
            # Fee is per hop
            total_fee_bps = dex_info.fee_bps * (len(path) - 1)
            
            return Quote(
                dex=dex_name,
                token_in=path[0],
                token_out=path[-1],
                amount_in=amount_in,
                amount_out=amount_out,
                price=price,
                fee_bps=total_fee_bps,
                timestamp=timestamp,
                is_valid=True,
            )
            
        except Exception as e:
            return Quote(
                dex=dex_name,
                token_in=path[0],
                token_out=path[-1],
                amount_in=amount_in,
                amount_out=Decimal(0),
                price=Decimal(0),
                fee_bps=dex_info.fee_bps * (len(path) - 1),
                timestamp=timestamp,
                is_valid=False,
                error=str(e)
            )
    
    def aggregate_quotes(
        self,
        token_in: str,
        token_out: str,
        amount_in: Decimal,
        dex_list: List[str] = None,
    ) -> AggregatedQuotes:
        """
        Get quotes from all DEXs in parallel and aggregate
        """
        timestamp = time.time()
        
        if dex_list is None:
            dex_list = list(DEXES.keys())
        
        quotes = {}
        
        # Parallel quote fetching
        with ThreadPoolExecutor(max_workers=len(dex_list)) as executor:
            future_to_dex = {
                executor.submit(
                    self.get_quote, dex, token_in, token_out, amount_in
                ): dex
                for dex in dex_list
            }
            
            for future in as_completed(future_to_dex):
                dex = future_to_dex[future]
                try:
                    quote = future.result()
                    if quote.is_valid:
                        quotes[dex] = quote
                except Exception:
                    pass
        
        if not quotes:
            return AggregatedQuotes(
                token_in=token_in,
                token_out=token_out,
                amount_in=amount_in,
                timestamp=timestamp,
            )
        
        # Find best and worst
        valid_quotes = [q for q in quotes.values() if q.is_valid]
        best = max(valid_quotes, key=lambda q: q.amount_out)
        worst = min(valid_quotes, key=lambda q: q.amount_out)
        
        # Calculate spread in basis points
        mid_price = (best.price + worst.price) / 2
        spread_bps = int(((best.price - worst.price) / mid_price) * 10000) if mid_price > 0 else 0
        
        return AggregatedQuotes(
            token_in=token_in,
            token_out=token_out,
            amount_in=amount_in,
            quotes=quotes,
            best_quote=best,
            worst_quote=worst,
            spread_bps=spread_bps,
            timestamp=timestamp,
        )
    
    def calculate_price_impact(
        self,
        dex_name: str,
        token_in: str,
        token_out: str,
        amount_in: Decimal,
    ) -> Decimal:
        """
        Calculate price impact for a trade
        Returns impact as a percentage (e.g., 0.5 = 0.5%)
        """
        reserves = self.get_reserves(dex_name, token_in, token_out)
        if not reserves:
            return Decimal(100)  # Unknown = assume worst
        
        # Determine which reserve is which
        if reserves.token0.lower() == token_in.lower():
            reserve_in = reserves.reserve0_human
            reserve_out = reserves.reserve1_human
        else:
            reserve_in = reserves.reserve1_human
            reserve_out = reserves.reserve0_human
        
        if reserve_in == 0:
            return Decimal(100)
        
        # Price impact ≈ amount_in / reserve_in * 100
        impact = (amount_in / reserve_in) * Decimal(100)
        
        return impact
    
    def find_arbitrage_opportunity(
        self,
        token_in: str,
        token_out: str,
        amount_in: Decimal,
    ) -> Optional[ArbitrageOpportunity]:
        """
        Find arbitrage opportunity between DEXs
        Buy on one DEX, sell on another
        """
        agg = self.aggregate_quotes(token_in, token_out, amount_in)
        
        if not agg.best_quote or not agg.worst_quote:
            return None
        
        if len(agg.quotes) < 2:
            return None
        
        # Best quote gives most out (good for buying)
        # For arbitrage: buy where cheap, sell where expensive
        # We need reverse quotes to properly calculate
        
        # Get reverse quotes (token_out -> token_in)
        reverse_agg = self.aggregate_quotes(token_out, token_in, agg.best_quote.amount_out)
        
        if not reverse_agg.best_quote:
            return None
        
        # Gross profit = final_amount - initial_amount
        final_amount = reverse_agg.best_quote.amount_out
        gross_profit = final_amount - amount_in
        
        if gross_profit <= 0:
            return None
        
        gross_profit_bps = int((gross_profit / amount_in) * 10000)
        
        return ArbitrageOpportunity(
            token_in=token_in,
            token_out=token_out,
            amount_in=amount_in,
            buy_dex=agg.best_quote.dex,
            sell_dex=reverse_agg.best_quote.dex,
            buy_price=agg.best_quote.price,
            sell_price=reverse_agg.best_quote.price,
            expected_out=final_amount,
            gross_profit=gross_profit,
            gross_profit_bps=gross_profit_bps,
            timestamp=time.time(),
        )


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def quote_amount_out(
    *,
    w3: Web3,
    router_addr: str,
    amount_in_human: float,
    path: list,
) -> float:
    """
    Legacy compatibility function
    Returns price = quote / base
    """
    from bot.pairs import DECIMALS
    
    router_addr = Web3.to_checksum_address(router_addr)
    router = w3.eth.contract(address=router_addr, abi=ROUTER_V2_ABI)

    amount_in = int(amount_in_human * (10 ** DECIMALS[path[0]]))
    amounts = router.functions.getAmountsOut(amount_in, path).call()

    amount_out_human = amounts[-1] / (10 ** DECIMALS[path[-1]])
    return amount_out_human / amount_in_human


