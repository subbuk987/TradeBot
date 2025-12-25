# bot/rpc_health.py
import time
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from bot.config import MAX_RPC_LATENCY, MAX_BLOCK_LAG

class RPCHealth:
    def __init__(self, rpc_url: str):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

        if not self.w3.is_connected():
            raise RuntimeError("RPC not connected")

    def check(self):
        try:
            start = time.time()
            latest = self.w3.eth.block_number
            latency = time.time() - start

            block = self.w3.eth.get_block("latest").number
            lag = abs(latest - block)

            if latency > MAX_RPC_LATENCY:
                return False, f"High latency {latency:.2f}s"

            if lag > MAX_BLOCK_LAG:
                return False, f"Block lag {lag}"

            return True, f"OK (latency={latency:.2f}s)"

        except Exception as e:
            return False, str(e)

