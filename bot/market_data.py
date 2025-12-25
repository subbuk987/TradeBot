# bot/market_data.py

from web3 import Web3
from decimal import Decimal, getcontext
from bot.uniswap_v3 import POOL_ABI, sqrt_price_x96_to_price_decimal
from bot.sushiswap import SushiSwapMarket

getcontext().prec = 80

ERC20_ABI = [
    {
        "name": "decimals",
        "outputs": [{"type": "uint8"}],
        "inputs": [],
        "stateMutability": "view",
        "type": "function",
    }
]

# Uniswap V3 USDC/WETH 0.3% pool (Polygon)
UNISWAP_POOL = Web3.to_checksum_address(
    "0x45dda9cb7c25131df268515131f647d726f50608"
)


class MarketData:
    def __init__(self, w3: Web3):
        self.w3 = w3

        self.uni = w3.eth.contract(address=UNISWAP_POOL, abi=POOL_ABI)

        # Token addresses
        self.token0 = self.uni.functions.token0().call()
        self.token1 = self.uni.functions.token1().call()

        # Token contracts
        self.token0_contract = w3.eth.contract(address=self.token0, abi=ERC20_ABI)
        self.token1_contract = w3.eth.contract(address=self.token1, abi=ERC20_ABI)

        # Token decimals
        self.dec0 = self.token0_contract.functions.decimals().call()
        self.dec1 = self.token1_contract.functions.decimals().call()

        # SushiSwap
        self.sushi = SushiSwapMarket(w3)

    def uniswap_usdc_per_weth(self) -> float:
        """
        Correct USDC per 1 WETH from Uniswap V3
        (fully normalized, production-grade)
        """

        sqrt_price_x96 = self.uni.functions.slot0().call()[0]
        price_raw = sqrt_price_x96_to_price_decimal(sqrt_price_x96)

        # price_raw = token1_raw / token0_raw
        # Normalize decimals
        scale = Decimal(10) ** (self.dec0 - self.dec1)
        price = price_raw * scale

        # Identify which side is WETH
        token0 = self.token0.lower()
        token1 = self.token1.lower()

        WETH = "0x7ceb23fd6bc0add59e62ac25578270cff1b9f619"

        if token0 == WETH:
            # price = token1 / WETH → already USDC/WETH
            usdc_per_weth = price
        elif token1 == WETH:
            # price = WETH / token0 → invert
            usdc_per_weth = Decimal(1) / price
        else:
            raise RuntimeError("WETH not found in Uniswap pool")

        return float(usdc_per_weth)

    def sushiswap_usdc_per_weth(self) -> float:
        return self.sushi.get_usdc_per_weth()

