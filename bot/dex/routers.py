# bot/dex/routers.py

from web3 import Web3

SUSHI_ROUTER = Web3.to_checksum_address(
    "0x1b02da8cb0d097eb8d57a175b88c7d8b47997506"
)

QUICK_ROUTER = Web3.to_checksum_address(
    "0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff"
)

ROUTER_ABI = [
    {
        "name": "getAmountsOut",
        "type": "function",
        "stateMutability": "view",
        "inputs": [
            {"name": "amountIn", "type": "uint256"},
            {"name": "path", "type": "address[]"},
        ],
        "outputs": [{"name": "amounts", "type": "uint256[]"}],
    }
]

