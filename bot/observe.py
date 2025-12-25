# bot/observe.py

from web3 import Web3

from bot.config import RPC_WS_PRIMARY
from bot.pairs import USDC_LEGACY as USDC, USDT
from bot.dex.pairs_polygon import POOLS
from bot.dex.routers import SUSHI_ROUTER, QUICK_ROUTER
from bot.quote_engine import quote_amount_out
from bot.reserves import read_reserve_in
from bot.decision import evaluate_trade


def run_once(trade_size_usdc: float = 500.0):

    w3 = Web3(Web3.HTTPProvider(RPC_WS_PRIMARY))

    dex_prices = {}
    reserves = []

    for (dex, base, quote), pair_addr in POOLS.items():

        if (base, quote) != (USDC, USDT):
            continue

        router_addr = {
            "sushi": SUSHI_ROUTER,
            "quick": QUICK_ROUTER,
        }.get(dex)

        try:
            price = quote_amount_out(
                w3=w3,
                router_addr=router_addr,
                amount_in_human=trade_size_usdc,
                path=[USDC, USDT],
            )
            dex_prices[dex] = price
        except Exception as e:
            print(f"[WARN] Quote failed on {dex}: {e}")
            continue

        try:
            reserve = read_reserve_in(
                w3=w3,
                pair_addr=pair_addr,
                base_token=USDC,
            )
            reserves.append(reserve)
        except Exception as e:
            print(f"[WARN] Reserve read failed on {dex}: {e}")

    if not dex_prices or not reserves:
        print("❌ Insufficient market data")
        return

    decision = evaluate_trade(
        w3=w3,
        base_token=USDC,
        quote_token=USDT,
        trade_size=trade_size_usdc,
        dex_prices=dex_prices,
        reserve_in=min(reserves),
    )

    print("==========================================")
    print("Stage 6 Observation (NO EXECUTION)")
    print("Trade size:", trade_size_usdc, "USDC")
    print("DEX prices:", dex_prices)
    print("USDC reserves:", reserves)
    print("Decision:", decision)
    print("==========================================")

