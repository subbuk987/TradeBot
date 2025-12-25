# bot/executor.py

import time
from web3 import Web3
from decimal import Decimal

from bot.router_abi import ROUTER_ABI
from bot.config import PRIVATE_KEY

# -------------------------------------------------
# Addresses (Polygon)
# -------------------------------------------------
SUSHI_ROUTER = Web3.to_checksum_address(
    "0x1b02da8cb0d097eb8d57a175b88c7d8b47997506"
)

USDC = Web3.to_checksum_address(
    "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"
)

WETH = Web3.to_checksum_address(
    "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619"
)

# -------------------------------------------------
# Minimal ERC20 ABI
# -------------------------------------------------
ERC20_ABI = [
    {
        "name": "approve",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "spender", "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "outputs": [{"name": "", "type": "bool"}],
    },
    {
        "name": "allowance",
        "type": "function",
        "stateMutability": "view",
        "inputs": [
            {"name": "owner", "type": "address"},
            {"name": "spender", "type": "address"},
        ],
        "outputs": [{"name": "", "type": "uint256"}],
    },
]

# -------------------------------------------------
# Constants (STRICT LIMITS)
# -------------------------------------------------
USDC_DECIMALS = 6
SLIPPAGE_BPS = 50          # 0.50%
GAS_LIMIT_APPROVE = 80_000
GAS_LIMIT_SWAP = 300_000
GAS_PRICE_GWEI = 100       # Legacy gasPrice (Polygon reliable)
DEADLINE_SECS = 120        # 2 minutes
CHAIN_ID = 137             # Polygon PoS


class Executor:
    def __init__(self, w3: Web3, address: str):
        self.w3 = w3
        self.address = Web3.to_checksum_address(address)

        self.router = w3.eth.contract(
            address=SUSHI_ROUTER,
            abi=ROUTER_ABI
        )

        self.usdc = w3.eth.contract(
            address=USDC,
            abi=ERC20_ABI
        )

    # -------------------------------------------------
    # Helpers
    # -------------------------------------------------
    def _nonce(self):
        # Use pending nonce to correctly replace stuck txs
        return self.w3.eth.get_transaction_count(self.address, "pending")

    def _sign_send(self, tx):
        """
        Sign and send a transaction.
        Web3.py v6+ compatible.
        """
        signed = self.w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        tx_hash = self.w3.eth.send_raw_transaction(
            signed.raw_transaction
        )
        return tx_hash.hex()

    # -------------------------------------------------
    # Approval logic (LEGACY gasPrice)
    # -------------------------------------------------
    def ensure_approval(self, amount_usdc: Decimal):
        """
        Ensure SushiSwap router is approved to spend USDC.
        Sends approval tx ONLY if needed.
        Uses legacy gasPrice for Polygon reliability.
        """
        amount = int(amount_usdc * (10 ** USDC_DECIMALS))

        allowance = self.usdc.functions.allowance(
            self.address,
            SUSHI_ROUTER
        ).call()

        if allowance >= amount:
            return None  # already approved

        tx = self.usdc.functions.approve(
            SUSHI_ROUTER,
            amount
        ).build_transaction({
            "from": self.address,
            "nonce": self._nonce(),           # same nonce replaces stuck tx
            "gas": GAS_LIMIT_APPROVE,
            "gasPrice": self.w3.to_wei(GAS_PRICE_GWEI, "gwei"),
            "chainId": CHAIN_ID,
        })

        return self._sign_send(tx)

    # -------------------------------------------------
    # ONE-SHOT SWAP (REAL TX, LEGACY gasPrice)
    # -------------------------------------------------
    def swap_usdc_to_weth_once(self, amount_usdc: Decimal):
        """
        Execute ONE real swap: USDC -> WETH
        Enforced limits:
        - Slippage protection
        - Gas cap
        - Deadline
        - Legacy gasPrice (Polygon-safe)
        """
        amount_in = int(amount_usdc * (10 ** USDC_DECIMALS))
        path = [USDC, WETH]

        # Quote
        amounts = self.router.functions.getAmountsOut(
            amount_in,
            path
        ).call()

        quoted_out = amounts[1]

        # Slippage protection
        min_out = int(
            quoted_out * (10_000 - SLIPPAGE_BPS) / 10_000
        )

        tx = self.router.functions.swapExactTokensForTokens(
            amount_in,
            min_out,
            path,
            self.address,
            int(time.time()) + DEADLINE_SECS
        ).build_transaction({
            "from": self.address,
            "nonce": self._nonce(),
            "gas": GAS_LIMIT_SWAP,
            "gasPrice": self.w3.to_wei(GAS_PRICE_GWEI, "gwei"),
            "chainId": CHAIN_ID,
        })

        return self._sign_send(tx)

