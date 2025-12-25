# bot/uniswap_v3.py
from decimal import Decimal, getcontext

getcontext().prec = 80

POOL_ABI = [
    {
        "name": "slot0",
        "outputs": [
            {"name": "sqrtPriceX96", "type": "uint160"},
            {"name": "tick", "type": "int24"},
            {"name": "", "type": "uint16"},
            {"name": "", "type": "uint16"},
            {"name": "", "type": "uint16"},
            {"name": "", "type": "uint8"},
            {"name": "", "type": "bool"},
        ],
        "inputs": [],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "name": "token0",
        "outputs": [{"type": "address"}],
        "inputs": [],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "name": "token1",
        "outputs": [{"type": "address"}],
        "inputs": [],
        "stateMutability": "view",
        "type": "function",
    },
]

Q192 = Decimal(2) ** 192

def sqrt_price_x96_to_price_decimal(sqrt_price_x96: int) -> Decimal:
    sp = Decimal(sqrt_price_x96)
    return (sp * sp) / Q192

