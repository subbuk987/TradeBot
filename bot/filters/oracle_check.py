# bot/filters/oracle_check.py
"""
Oracle Price Guard
Validates DEX prices against Chainlink oracle prices
Prevents trading on manipulated or stale pools
"""

from dataclasses import dataclass
from web3 import Web3
from bot.pairs import TOKENS, get_symbol

# --------- Chainlink Aggregator ABI (minimal) ---------
AGGREGATOR_ABI = [
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

# --------- Chainlink Feeds (Polygon) ---------
# Prices are USD-denominated
CHAINLINK_FEEDS = {
    # Stablecoins
    "USDC": Web3.to_checksum_address("0xfE4A8cc5b5B2366C1B58Bea3858e81843581b2F7"),
    "USDC.e": Web3.to_checksum_address("0xfE4A8cc5b5B2366C1B58Bea3858e81843581b2F7"),
    "USDT": Web3.to_checksum_address("0x0A6513e40db6EB1b165753AD52E80663aeA50545"),
    "DAI": Web3.to_checksum_address("0x4746DeC9e833A82EC7C2C1356372CcF2cfcD2F3D"),
    
    # Major tokens
    "WMATIC": Web3.to_checksum_address("0xAB594600376Ec9fD91F8e885dADF0CE036862dE0"),
    "WETH": Web3.to_checksum_address("0xF9680D99D6C9589e2a93a78A04A279e509205945"),
    "WBTC": Web3.to_checksum_address("0xc907E116054Ad103354f2D350FD2514433D57F6f"),
    "LINK": Web3.to_checksum_address("0xd9FFdb71EbE7496cC440152d43986Aae0AB76665"),
    "AAVE": Web3.to_checksum_address("0x72484B12719E23115761D5DA1646945632979bB6"),
    "CRV": Web3.to_checksum_address("0x336584C8E6Dc19637A5b36206B1c79923111b405"),
    "SUSHI": Web3.to_checksum_address("0x49B0c695039243BBfEb8EcD054EB70061fd54aa0"),
    "UNI": Web3.to_checksum_address("0xdf0Fb4e4F928d2dCB76f438575fDD8682386e13C"),
}


@dataclass
class OracleResult:
    """Result of oracle price check"""
    ok: bool
    oracle_price: float
    quoted_price: float
    deviation_pct: float
    reason: str = ""


def _read_chainlink_price(w3: Web3, feed_addr: str) -> float:
    """Read price from Chainlink feed"""
    feed = w3.eth.contract(address=feed_addr, abi=AGGREGATOR_ABI)
    _, answer, _, updated_at, _ = feed.functions.latestRoundData().call()
    decimals = feed.functions.decimals().call()
    
    # Check staleness (price should be updated within last hour)
    import time
    if time.time() - updated_at > 3600:
        raise ValueError("Stale oracle price")
    
    return float(answer) / (10 ** decimals)


def oracle_price_guard(
    w3: Web3,
    base_token: str,
    quote_token: str,
    quoted_price: float,
    max_deviation_pct: float = 5.0,  # Allow more deviation for volatile pairs
) -> OracleResult:
    """
    Compare DEX price against Chainlink oracle
    
    quoted_price: price of base in terms of quote (quote/base)
    Example: WMATIC/USDC price of 0.50 means 1 WMATIC = 0.50 USDC
    
    Returns OracleResult with pass/fail and deviation info
    """
    
    # Resolve symbols from addresses
    base_sym = get_symbol(base_token)
    quote_sym = get_symbol(quote_token)

    # Check if we have Chainlink feeds for both tokens
    if base_sym not in CHAINLINK_FEEDS:
        return OracleResult(
            ok=True,  # Pass if no oracle (can't verify)
            oracle_price=0.0,
            quoted_price=quoted_price,
            deviation_pct=0.0,
            reason=f"No Chainlink feed for {base_sym} - skipping oracle check",
        )
    
    if quote_sym not in CHAINLINK_FEEDS:
        return OracleResult(
            ok=True,
            oracle_price=0.0,
            quoted_price=quoted_price,
            deviation_pct=0.0,
            reason=f"No Chainlink feed for {quote_sym} - skipping oracle check",
        )

    try:
        # Get USD prices from Chainlink
        base_usd = _read_chainlink_price(w3, CHAINLINK_FEEDS[base_sym])
        quote_usd = _read_chainlink_price(w3, CHAINLINK_FEEDS[quote_sym])

        # Calculate oracle price (base in terms of quote)
        oracle_price = base_usd / quote_usd if quote_usd > 0 else 0

        # Calculate deviation
        if oracle_price > 0:
            deviation = abs(quoted_price - oracle_price) / oracle_price * 100.0
        else:
            deviation = 100.0

        if deviation > max_deviation_pct:
            return OracleResult(
                ok=False,
                oracle_price=oracle_price,
                quoted_price=quoted_price,
                deviation_pct=deviation,
                reason=f"Oracle deviation {deviation:.2f}% > {max_deviation_pct:.2f}%",
            )

        return OracleResult(
            ok=True,
            oracle_price=oracle_price,
            quoted_price=quoted_price,
            deviation_pct=deviation,
        )
        
    except Exception as e:
        # If oracle check fails, be conservative and reject
        return OracleResult(
            ok=False,
            oracle_price=0.0,
            quoted_price=quoted_price,
            deviation_pct=100.0,
            reason=f"Oracle read failed: {str(e)}",
        )

