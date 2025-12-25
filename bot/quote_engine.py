# bot/quote_engine.py

from web3 import Web3
from bot.dex.routers import ROUTER_ABI
from bot.pairs import DECIMALS


def quote_amount_out(
    *,
    w3: Web3,
    router_addr: str,
    amount_in_human: float,
    path: list,
) -> float:
    """
    Returns price = quote / base
    """

    router_addr = Web3.to_checksum_address(router_addr)
    router = w3.eth.contract(address=router_addr, abi=ROUTER_ABI)

    amount_in = int(amount_in_human * (10 ** DECIMALS[path[0]]))
    amounts = router.functions.getAmountsOut(amount_in, path).call()

    amount_out_human = amounts[-1] / (10 ** DECIMALS[path[-1]])
    return amount_out_human / amount_in_human

