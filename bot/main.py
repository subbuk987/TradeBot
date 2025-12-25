# bot/main.py

from decimal import Decimal
from bot.rpc_health import RPCHealth
from bot.market_data import MarketData
from bot.executor import Executor
from bot.config import RPC_WS_PRIMARY, PUBLIC_ADDRESS

TRADE_AMOUNT_USDC = Decimal("0.50")


def main():
    print("🚀 Stage 4C: ONE real transaction (guarded)")

    rpc = RPCHealth(RPC_WS_PRIMARY)
    ok, status = rpc.check()
    if not ok:
        print("❌ RPC unhealthy:", status)
        return
    print("✅ RPC healthy:", status)

    executor = Executor(rpc.w3, PUBLIC_ADDRESS)

    # Approval (if needed)
    print("🔎 Checking approval...")
    txh = executor.ensure_approval(TRADE_AMOUNT_USDC)
    if txh:
        print("🟡 Approval sent:", txh)
        print("⏳ Wait for approval to confirm, then re-run Stage 4C.")
        return
    print("✅ Approval OK")

    # One-shot swap
    print(f"🔁 Executing swap: {TRADE_AMOUNT_USDC} USDC → WETH")
    txh = executor.swap_usdc_to_weth_once(TRADE_AMOUNT_USDC)
    print("🧾 Swap tx sent:", txh)

    print("🛑 Auto-pause engaged. Stage 4C complete.")


if __name__ == "__main__":
    main()

