# bot/simulator.py

from web3 import Web3
from decimal import Decimal

# -----------------------------
# SushiSwap Router (Polygon)
# -----------------------------
SUSHI_ROUTER = Web3.to_checksum_address(
    "0x1b02da8cb0d097eb8d57a175b88c7d8b47997506"
)

# -----------------------------
# Minimal ABI (read-only)
# -----------------------------
ROUTER_ABI = [
    {
        "name": "getAmountsOut",
        "outputs": [{"type": "uint256[]"}],
        "inputs": [
            {"name": "amountIn", "type": "uint256"},
            {"name": "path", "type": "address[]"},
        ],
        "stateMutability": "view",
        "type": "function",
    }
]

# -----------------------------
# Token addresses (Polygon)
# -----------------------------
USDC = Web3.to_checksum_address(
    "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
)

WETH = Web3.to_checksum_address(
    "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619"
)

USDC_DECIMALS = 6
WETH_DECIMALS = 18


class SwapSimulator:
    def __init__(self, w3: Web3):
        self.w3 = w3
        self.router = w3.eth.contract(
            address=SUSHI_ROUTER,
            abi=ROUTER_ABI
        )

    def simulate_usdc_to_weth(self, usdc_amount: Decimal) -> Decimal:
        """
        Simulates USDC → WETH using getAmountsOut
        NO transaction is sent.
        """

        # Convert USDC to base units
        amount_in = int(usdc_amount * (10 ** USDC_DECIMALS))

        path = [USDC, WETH]

        amounts = self.router.functions.getAmountsOut(
            amount_in,
            path
        ).call()

        # Convert WETH back to human units
        weth_out = Decimal(amounts[1]) / (10 ** WETH_DECIMALS)

        return weth_out

