# bot/dex/pairs_polygon.py

from web3 import Web3
from bot.pairs import USDC_LEGACY, USDT

POOLS = {
    # SushiSwap USDC / USDT
    ("sushi", USDC_LEGACY, USDT): Web3.to_checksum_address(
        "0x4b1F1e2435A9C96f7330FAea190Ef6A7C8D70001"
    ),

    # QuickSwap USDC / USDT
    ("quick", USDC_LEGACY, USDT): Web3.to_checksum_address(
        "0x2cF7252e74036d1Da831d11089D326296e64a728"
    ),
}

