# bot/sushiswap.py
from web3 import Web3

PAIR_ABI = [
    {
        "name": "getReserves",
        "outputs": [
            {"name": "_reserve0", "type": "uint112"},
            {"name": "_reserve1", "type": "uint112"},
            {"name": "_blockTimestampLast", "type": "uint32"},
        ],
        "inputs": [],
        "stateMutability": "view",
        "type": "function",
    }
]

SUSHI_USDC_WETH_PAIR = Web3.to_checksum_address(
    "0x34965ba0ac2451a34a0471f04cca3f990b8dea27"
)

DECIMAL_ADJUST = 10 ** 12  # 18 - 6

class SushiSwapMarket:
    def __init__(self, w3: Web3):
        self.pair = w3.eth.contract(
            address=SUSHI_USDC_WETH_PAIR,
            abi=PAIR_ABI
        )

    def get_usdc_per_weth(self) -> float:
        r0, r1, _ = self.pair.functions.getReserves().call()
        return (r0 * DECIMAL_ADJUST) / r1

