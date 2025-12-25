# bot/pairs.py
"""
Comprehensive Token & DEX Registry for Polygon
Includes all major tokens and trading pairs for arbitrage
"""

from web3 import Web3
from dataclasses import dataclass
from typing import Dict, List, Tuple, Set

# =============================================================================
# TOKEN ADDRESSES (Polygon Mainnet - All Checksummed)
# =============================================================================

# Stablecoins
USDC_NATIVE = Web3.to_checksum_address("0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359")
USDC_LEGACY = Web3.to_checksum_address("0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174")
USDT = Web3.to_checksum_address("0xc2132D05D31c914a87C6611C10748AEb04B58e8F")
DAI = Web3.to_checksum_address("0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063")
FRAX = Web3.to_checksum_address("0x45c32fA6DF82ead1e2EF74d17b76547EDdFaFF89")
MAI = Web3.to_checksum_address("0xa3Fa99A148fA48D14Ed51d610c367C61876997F1")

# Native/Wrapped
WMATIC = Web3.to_checksum_address("0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270")
WETH = Web3.to_checksum_address("0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619")
WBTC = Web3.to_checksum_address("0x1BFD67037B42Cf73acF2047067bd4F2C47D9BfD6")

# Major DeFi Tokens
LINK = Web3.to_checksum_address("0x53E0bca35eC356BD5ddDFebbD1Fc0fD03FaBad39")
AAVE = Web3.to_checksum_address("0xD6DF932A45C0f255f85145f286eA0b292B21C90B")
CRV = Web3.to_checksum_address("0x172370d5Cd63279eFa6d502DAB29171933a610AF")
SUSHI = Web3.to_checksum_address("0x0b3F868E0BE5597D5DB7fEB59E1CADBb0fdDa50a")
UNI = Web3.to_checksum_address("0xb33EaAd8d922B1083446DC23f610c2567fB5180f")
BAL = Web3.to_checksum_address("0x9a71012B13CA4d3D0Cdc72A177DF3ef03b0E76A3")
QUICK = Web3.to_checksum_address("0xB5C064F955D8e7F38fE0460C556a72987494eE17")

# Liquid Staking
STMATIC = Web3.to_checksum_address("0x3A58a54C066FdC0f2D55FC9C89F0415C92eBf3C4")
MATICX = Web3.to_checksum_address("0xfa68FB4628DFF1028CFEc22b4162FCcd0d45efb6")

# =============================================================================
# TOKEN METADATA
# =============================================================================

@dataclass
class TokenInfo:
    address: str
    symbol: str
    decimals: int
    is_stable: bool
    chainlink_feed: str = None  # Chainlink price feed address


TOKENS: Dict[str, TokenInfo] = {
    USDC_NATIVE: TokenInfo(USDC_NATIVE, "USDC", 6, True, "0xfE4A8cc5b5B2366C1B58Bea3858e81843581b2F7"),
    USDC_LEGACY: TokenInfo(USDC_LEGACY, "USDC.e", 6, True, "0xfE4A8cc5b5B2366C1B58Bea3858e81843581b2F7"),
    USDT: TokenInfo(USDT, "USDT", 6, True, "0x0A6513e40db6EB1b165753AD52E80663aeA50545"),
    DAI: TokenInfo(DAI, "DAI", 18, True, "0x4746DeC9e833A82EC7C2C1356372CcF2cfcD2F3D"),
    FRAX: TokenInfo(FRAX, "FRAX", 18, True, None),
    MAI: TokenInfo(MAI, "MAI", 18, True, None),
    WMATIC: TokenInfo(WMATIC, "WMATIC", 18, False, "0xAB594600376Ec9fD91F8e885dADF0CE036862dE0"),
    WETH: TokenInfo(WETH, "WETH", 18, False, "0xF9680D99D6C9589e2a93a78A04A279e509205945"),
    WBTC: TokenInfo(WBTC, "WBTC", 8, False, "0xc907E116054Ad103354f2D350FD2514433D57F6f"),
    LINK: TokenInfo(LINK, "LINK", 18, False, "0xd9FFdb71EbE7496cC440152d43986Aae0AB76665"),
    AAVE: TokenInfo(AAVE, "AAVE", 18, False, "0x72484B12719E23115761D5DA1646945632979bB6"),
    CRV: TokenInfo(CRV, "CRV", 18, False, "0x336584C8E6Dc19637A5b36206B1c79923111b405"),
    SUSHI: TokenInfo(SUSHI, "SUSHI", 18, False, "0x49B0c695039243BBfEb8EcD054EB70061fd54aa0"),
    UNI: TokenInfo(UNI, "UNI", 18, False, "0xdf0Fb4e4F928d2dCB76f438575fDD8682386e13C"),
    QUICK: TokenInfo(QUICK, "QUICK", 18, False, None),
    STMATIC: TokenInfo(STMATIC, "stMATIC", 18, False, None),
    MATICX: TokenInfo(MATICX, "MaticX", 18, False, None),
}

# Legacy compatibility
DECIMALS = {addr: info.decimals for addr, info in TOKENS.items()}
SYMBOL_BY_ADDRESS = {addr: info.symbol for addr, info in TOKENS.items()}

# =============================================================================
# DEX ROUTER ADDRESSES
# =============================================================================

@dataclass
class DexInfo:
    name: str
    router: str
    factory: str
    fee_bps: int
    version: str  # "v2" or "v3"


DEXES: Dict[str, DexInfo] = {
    "quickswap": DexInfo(
        name="QuickSwap",
        router=Web3.to_checksum_address("0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff"),
        factory=Web3.to_checksum_address("0x5757371414417b8C6CAad45bAeF941aBc7d3Ab32"),
        fee_bps=30,
        version="v2"
    ),
    "sushiswap": DexInfo(
        name="SushiSwap",
        router=Web3.to_checksum_address("0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506"),
        factory=Web3.to_checksum_address("0xc35DADB65012eC5796536bD9864eD8773aBc74C4"),
        fee_bps=30,
        version="v2"
    ),
    "apeswap": DexInfo(
        name="ApeSwap",
        router=Web3.to_checksum_address("0xC0788A3aD43d79aa53B09c2EaCc313A787d1d607"),
        factory=Web3.to_checksum_address("0xCf083Be4164828f00cAE704EC15a36D711491284"),
        fee_bps=20,
        version="v2"
    ),
    "dfyn": DexInfo(
        name="DFYN",
        router=Web3.to_checksum_address("0xA102072A4C07F06EC3B4900FDC4C7B80b6c57429"),
        factory=Web3.to_checksum_address("0xE7Fb3e833eFE5F9c441105EB65Ef8b261266423B"),
        fee_bps=30,
        version="v2"
    ),
    "meshswap": DexInfo(
        name="MeshSwap",
        router=Web3.to_checksum_address("0x10f4A785F458Bc144e3706575924889954946639"),
        factory=Web3.to_checksum_address("0x9F3044f7F9FC8bC9eD615d54845b4577B833282d"),
        fee_bps=30,
        version="v2"
    ),
}

# Quick access to router addresses
SUSHI_ROUTER = DEXES["sushiswap"].router
QUICK_ROUTER = DEXES["quickswap"].router

# =============================================================================
# AAVE V3 FLASH LOAN CONFIG
# =============================================================================

AAVE_V3_POOL = Web3.to_checksum_address("0x794a61358D6845594F94dc1DB02A252b5b4814aD")
AAVE_FLASH_FEE_BPS = 5  # 0.05%

# Tokens available for flash loans on Aave V3 Polygon
FLASH_LOAN_TOKENS = {
    USDC_LEGACY,  # Highest liquidity
    USDC_NATIVE,
    USDT,
    DAI,
    WMATIC,
    WETH,
    WBTC,
    LINK,
    AAVE,
}

# =============================================================================
# TRADING PAIRS CONFIGURATION
# =============================================================================

# High-volume pairs for arbitrage (base, quote)
# Ordered by typical volume/liquidity
HIGH_VOLUME_PAIRS: List[Tuple[str, str]] = [
    # WMATIC pairs (highest volume on Polygon)
    (WMATIC, USDC_LEGACY),
    (WMATIC, USDC_NATIVE),
    (WMATIC, USDT),
    (WMATIC, WETH),
    (WMATIC, DAI),
    
    # WETH pairs
    (WETH, USDC_LEGACY),
    (WETH, USDC_NATIVE),
    (WETH, USDT),
    (WETH, WBTC),
    
    # Stablecoin pairs
    (USDC_LEGACY, USDT),
    (USDC_LEGACY, DAI),
    (USDC_NATIVE, USDT),
    (DAI, USDT),
    
    # DeFi token pairs
    (LINK, WMATIC),
    (LINK, WETH),
    (AAVE, WMATIC),
    (AAVE, WETH),
    (CRV, WMATIC),
    (SUSHI, WMATIC),
    (QUICK, WMATIC),
]

# Triangular arbitrage routes (start token, intermediate, end = start)
TRIANGULAR_ROUTES: List[Tuple[str, str, str]] = [
    # USDC → WMATIC → WETH → USDC
    (USDC_LEGACY, WMATIC, WETH),
    (USDC_NATIVE, WMATIC, WETH),
    
    # USDC → WETH → WMATIC → USDC
    (USDC_LEGACY, WETH, WMATIC),
    (USDC_NATIVE, WETH, WMATIC),
    
    # USDC → WMATIC → LINK → USDC
    (USDC_LEGACY, WMATIC, LINK),
    
    # USDC → WETH → WBTC → USDC
    (USDC_LEGACY, WETH, WBTC),
    
    # WMATIC → WETH → LINK → WMATIC
    (WMATIC, WETH, LINK),
    
    # WMATIC → USDC → WETH → WMATIC
    (WMATIC, USDC_LEGACY, WETH),
    
    # DAI → USDC → WMATIC → DAI
    (DAI, USDC_LEGACY, WMATIC),
]

# Safe pairs whitelist (pairs verified for trading)
SAFE_PAIRS: Set[Tuple[str, str]] = set(HIGH_VOLUME_PAIRS)

# Add reverse pairs
for base, quote in list(SAFE_PAIRS):
    SAFE_PAIRS.add((quote, base))

# =============================================================================
# POOL ADDRESSES (Known liquidity pools)
# =============================================================================

# QuickSwap Pools
QUICKSWAP_POOLS = {
    (WMATIC, USDC_LEGACY): Web3.to_checksum_address("0x6e7a5FAFcec6BB1e78bAE2A1F0B612012BF14827"),
    (WMATIC, USDT): Web3.to_checksum_address("0x604229c960e5CACF2aaEAc8Be68Ac07BA9dF81c3"),
    (WMATIC, WETH): Web3.to_checksum_address("0xadbF1854e5883eB8aa7BAf50705338739e558E5b"),
    (WETH, USDC_LEGACY): Web3.to_checksum_address("0x853Ee4b2A13f8a742d64C8F088bE7bA2131f670d"),
    (USDC_LEGACY, USDT): Web3.to_checksum_address("0x2cF7252e74036d1Da831d11089D326296e64a728"),
}

# SushiSwap Pools  
SUSHISWAP_POOLS = {
    (WMATIC, USDC_LEGACY): Web3.to_checksum_address("0xcd353F79d9FADe311fC3119B841e1f456b54e858"),
    (WMATIC, WETH): Web3.to_checksum_address("0xc4e595acDD7d12feC385E5dA5D43160e8A0bAC0E"),
    (WETH, USDC_LEGACY): Web3.to_checksum_address("0x34965ba0ac2451A34a0471F04CCa3F990b8dea27"),
    (USDC_LEGACY, USDT): Web3.to_checksum_address("0x4B1F1e2435A9C96f7330FAea190Ef6A7C8D70001"),
}

# Combined pool registry
POOLS = {
    ("quickswap", *k): v for k, v in QUICKSWAP_POOLS.items()
}
POOLS.update({
    ("sushiswap", *k): v for k, v in SUSHISWAP_POOLS.items()
})


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_token_info(address: str) -> TokenInfo:
    """Get token info by address (checksummed or not)"""
    addr = Web3.to_checksum_address(address)
    return TOKENS.get(addr)


def get_decimals(address: str) -> int:
    """Get token decimals"""
    info = get_token_info(address)
    return info.decimals if info else 18


def get_symbol(address: str) -> str:
    """Get token symbol"""
    info = get_token_info(address)
    return info.symbol if info else "UNKNOWN"


def is_stablecoin(address: str) -> bool:
    """Check if token is a stablecoin"""
    info = get_token_info(address)
    return info.is_stable if info else False


def get_dex_info(dex_name: str) -> DexInfo:
    """Get DEX info by name"""
    return DEXES.get(dex_name.lower())


def get_all_dex_names() -> List[str]:
    """Get list of all DEX names"""
    return list(DEXES.keys())

