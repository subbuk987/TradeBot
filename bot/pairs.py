# bot/pairs.py

from web3 import Web3

# -------- Tokens (Polygon) --------

USDC_NATIVE  = Web3.to_checksum_address(
    "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"
)

USDC_LEGACY  = Web3.to_checksum_address(
    "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
)

USDT = Web3.to_checksum_address(
    "0xC2132D05D31c914a87C6611C10748AEb04B58e8F"
)

DAI = Web3.to_checksum_address(
    "0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063"
)

WMATIC = Web3.to_checksum_address(
    "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270"
)

# -------- Decimals --------

DECIMALS = {
    USDC_NATIVE: 6,
    USDC_LEGACY: 6,
    USDT: 6,
    DAI: 18,
    WMATIC: 18,
}

# -------- Safe trading pairs --------
SAFE_PAIRS = {
    (USDC_LEGACY, USDT),
    (USDC_LEGACY, DAI),
}

# -------- Symbol resolution --------
SYMBOL_BY_ADDRESS = {
    USDC_NATIVE: "USDC_NATIVE",
    USDC_LEGACY: "USDC",
    USDT: "USDT",
    DAI: "DAI",
    WMATIC: "WMATIC",
}

