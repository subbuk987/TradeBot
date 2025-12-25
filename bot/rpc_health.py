# bot/rpc_health.py
"""
RPC Health Monitoring
Checks RPC connection, latency, and block synchronization
"""

import time
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from bot.config import MAX_RPC_LATENCY, MAX_BLOCK_LAG, RPC_ENDPOINTS


class RPCHealth:
    """
    Monitor RPC health and provide failover
    """
    
    def __init__(self, rpc_url: str = None):
        if rpc_url is None:
            rpc_url = RPC_ENDPOINTS[0]
            
        self.rpc_url = rpc_url
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

        if not self.w3.is_connected():
            raise RuntimeError(f"RPC not connected: {rpc_url}")

    def check(self) -> tuple:
        """
        Check RPC health
        Returns (is_healthy: bool, status_message: str)
        """
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

            return True, f"OK (latency={latency:.2f}s, block={latest})"

        except Exception as e:
            return False, str(e)
    
    def get_chain_id(self) -> int:
        """Get chain ID"""
        return self.w3.eth.chain_id
    
    def get_gas_price(self) -> int:
        """Get current gas price in wei"""
        return self.w3.eth.gas_price
    
    def get_gas_price_gwei(self) -> float:
        """Get current gas price in gwei"""
        return self.w3.eth.gas_price / 10**9


def find_healthy_rpc() -> tuple:
    """
    Find a healthy RPC from the list of endpoints
    Returns (Web3 instance, rpc_url) or (None, None) if all fail
    """
    for rpc_url in RPC_ENDPOINTS:
        try:
            rpc = RPCHealth(rpc_url)
            ok, status = rpc.check()
            if ok:
                return rpc.w3, rpc_url
        except Exception:
            continue
    
    return None, None

