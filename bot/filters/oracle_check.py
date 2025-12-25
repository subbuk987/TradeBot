# bot/filters/oracle_check.py

from dataclasses import dataclass
from web3 import Web3
from bot.pairs import DECIMALS
from bot.pairs import SYMBOL_BY_ADDRESS

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
    "USDC": Web3.to_checksum_address("0xfe4a8cc5b5b2366c1b58bea3858e81843581b2f7"),
    "USDT": Web3.to_checksum_address("0x0a6513e40db6eb1b165753ad52e80663aea50545"),
    "DAI":  Web3.to_checksum_address("0x4746dec9e833a82ec7c2c1356372ccf2cfcd2f3d"),

    # WMATIC
    "WMATIC": Web3.to_checksum_address("0xab594600376ec9fd91f8e885dadf0ce036862de0"),
}




@dataclass
class OracleResult:
    ok: bool
    oracle_price: float
    quoted_price: float
    deviation_pct: float
    reason: str = ""


def _read_chainlink_price(w3: Web3, feed_addr: str) -> float:
    feed = w3.eth.contract(address=feed_addr, abi=AGGREGATOR_ABI)
    _, answer, _, _, _ = feed.functions.latestRoundData().call()
    decimals = feed.functions.decimals().call()
    return float(answer) / (10 ** decimals)


def oracle_price_guard(
    w3: Web3,
    base_token: str,
    quote_token: str,
    quoted_price: float,
    max_deviation_pct: float = 1.0,
) -> OracleResult:
    """
    quoted_price: price of base in terms of quote (quote/base)
    Example: USDC/USDT ≈ 1.000
    """

    # Resolve symbols
    base_sym = SYMBOL_BY_ADDRESS.get(base_token)
    quote_sym = SYMBOL_BY_ADDRESS.get(quote_token)

    if base_sym not in CHAINLINK_FEEDS or quote_sym not in CHAINLINK_FEEDS:
        return OracleResult(
            ok=False,
            oracle_price=0.0,
            quoted_price=quoted_price,
            deviation_pct=100.0,
            reason="Missing Chainlink feed",
        )

    base_usd = _read_chainlink_price(w3, CHAINLINK_FEEDS[base_sym])
    quote_usd = _read_chainlink_price(w3, CHAINLINK_FEEDS[quote_sym])

    oracle_price = base_usd / quote_usd

    deviation = abs(quoted_price - oracle_price) / oracle_price * 100.0

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

