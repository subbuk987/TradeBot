# bot/gas.py

from web3 import Web3

# Conservative Polygon assumptions
GAS_LIMIT_SWAP = 180_000
GAS_LIMIT_APPROVAL = 50_000


def estimate_gas_cost_usd(
    *,
    w3: Web3,
    gas_price_gwei: float,
    matic_price_usd: float,
    include_approval: bool = False,
) -> float:

    gas_units = GAS_LIMIT_SWAP
    if include_approval:
        gas_units += GAS_LIMIT_APPROVAL

    gas_cost_matic = gas_units * gas_price_gwei * 1e-9
    return gas_cost_matic * matic_price_usd

