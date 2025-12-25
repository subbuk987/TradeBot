# bot/reserves.py

from web3 import Web3
from bot.dex.pair_abi import PAIR_ABI
from bot.pairs import DECIMALS


def read_reserve_in(
    *,
    w3: Web3,
    pair_addr: str,
    base_token: str,
) -> float:

    pair = w3.eth.contract(address=pair_addr, abi=PAIR_ABI)
    r0, r1, _ = pair.functions.getReserves().call()
    t0 = pair.functions.token0().call()
    t1 = pair.functions.token1().call()

    if base_token.lower() == t0.lower():
        return r0 / (10 ** DECIMALS[base_token])
    elif base_token.lower() == t1.lower():
        return r1 / (10 ** DECIMALS[base_token])
    else:
        raise ValueError("Base token not in pool")

