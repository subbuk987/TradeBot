# bot/flash_loan.py
"""
Aave V3 Flash Loan Integration for Zero-Capital Arbitrage
This module handles flash loan borrowing and repayment logic
"""

from web3 import Web3
from decimal import Decimal
from dataclasses import dataclass
from typing import List, Optional, Tuple
import json

from bot.pairs import (
    TOKENS, FLASH_LOAN_TOKENS, AAVE_V3_POOL, AAVE_FLASH_FEE_BPS,
    get_decimals, get_symbol
)

# =============================================================================
# AAVE V3 POOL ABI (Flash Loan Related Functions)
# =============================================================================

AAVE_POOL_ABI = [
    # Flash loan function
    {
        "name": "flashLoan",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "receiverAddress", "type": "address"},
            {"name": "assets", "type": "address[]"},
            {"name": "amounts", "type": "uint256[]"},
            {"name": "interestRateModes", "type": "uint256[]"},
            {"name": "onBehalfOf", "type": "address"},
            {"name": "params", "type": "bytes"},
            {"name": "referralCode", "type": "uint16"},
        ],
        "outputs": [],
    },
    # Flash loan simple (single asset)
    {
        "name": "flashLoanSimple",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "receiverAddress", "type": "address"},
            {"name": "asset", "type": "address"},
            {"name": "amount", "type": "uint256"},
            {"name": "params", "type": "bytes"},
            {"name": "referralCode", "type": "uint16"},
        ],
        "outputs": [],
    },
    # Get reserve data (to check available liquidity)
    {
        "name": "getReserveData",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "asset", "type": "address"}],
        "outputs": [
            {
                "components": [
                    {"name": "configuration", "type": "uint256"},
                    {"name": "liquidityIndex", "type": "uint128"},
                    {"name": "currentLiquidityRate", "type": "uint128"},
                    {"name": "variableBorrowIndex", "type": "uint128"},
                    {"name": "currentVariableBorrowRate", "type": "uint128"},
                    {"name": "currentStableBorrowRate", "type": "uint128"},
                    {"name": "lastUpdateTimestamp", "type": "uint40"},
                    {"name": "id", "type": "uint16"},
                    {"name": "aTokenAddress", "type": "address"},
                    {"name": "stableDebtTokenAddress", "type": "address"},
                    {"name": "variableDebtTokenAddress", "type": "address"},
                    {"name": "interestRateStrategyAddress", "type": "address"},
                    {"name": "accruedToTreasury", "type": "uint128"},
                    {"name": "unbacked", "type": "uint128"},
                    {"name": "isolationModeTotalDebt", "type": "uint128"},
                ],
                "name": "",
                "type": "tuple",
            }
        ],
    },
    # Get flash loan premium
    {
        "name": "FLASHLOAN_PREMIUM_TOTAL",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "uint128"}],
    },
]

# aToken ABI for checking available liquidity
ATOKEN_ABI = [
    {
        "name": "totalSupply",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "uint256"}],
    },
    {
        "name": "balanceOf",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "account", "type": "address"}],
        "outputs": [{"name": "", "type": "uint256"}],
    },
]


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class FlashLoanQuote:
    """Quote for a flash loan"""
    token: str
    symbol: str
    amount: int  # In wei
    amount_human: Decimal
    fee_amount: int  # In wei
    fee_human: Decimal
    fee_bps: int
    available_liquidity: int
    is_available: bool
    reason: str = ""


@dataclass
class FlashLoanParams:
    """Parameters for executing a flash loan"""
    receiver: str  # Contract that will receive and execute the arbitrage
    token: str
    amount: int
    params: bytes  # Encoded arbitrage parameters
    

# =============================================================================
# FLASH LOAN MANAGER
# =============================================================================

class FlashLoanManager:
    """
    Manages flash loan operations with Aave V3
    """
    
    def __init__(self, w3: Web3):
        self.w3 = w3
        self.pool = w3.eth.contract(
            address=AAVE_V3_POOL,
            abi=AAVE_POOL_ABI
        )
        self._fee_cache = None
        self._liquidity_cache = {}
        
    def get_flash_loan_fee_bps(self) -> int:
        """Get the current flash loan fee in basis points"""
        if self._fee_cache is None:
            try:
                # FLASHLOAN_PREMIUM_TOTAL returns fee in basis points
                self._fee_cache = self.pool.functions.FLASHLOAN_PREMIUM_TOTAL().call()
            except Exception:
                # Fallback to known fee
                self._fee_cache = AAVE_FLASH_FEE_BPS
        return self._fee_cache
    
    def get_available_liquidity(self, token: str) -> int:
        """Get available liquidity for flash loans"""
        token = Web3.to_checksum_address(token)
        
        try:
            reserve_data = self.pool.functions.getReserveData(token).call()
            atoken_address = reserve_data[8]  # aTokenAddress
            
            # Get aToken contract
            atoken = self.w3.eth.contract(
                address=atoken_address,
                abi=ATOKEN_ABI
            )
            
            # Available liquidity = total supply of aToken
            liquidity = atoken.functions.totalSupply().call()
            return liquidity
            
        except Exception as e:
            # Return 0 if we can't determine liquidity
            return 0
    
    def calculate_fee(self, amount: int, token: str) -> Tuple[int, Decimal]:
        """Calculate flash loan fee"""
        fee_bps = self.get_flash_loan_fee_bps()
        fee_amount = (amount * fee_bps) // 10000
        
        decimals = get_decimals(token)
        fee_human = Decimal(fee_amount) / Decimal(10 ** decimals)
        
        return fee_amount, fee_human
    
    def quote_flash_loan(
        self,
        token: str,
        amount_human: Decimal
    ) -> FlashLoanQuote:
        """
        Get a quote for a flash loan
        Returns availability, fees, and liquidity info
        """
        token = Web3.to_checksum_address(token)
        
        # Check if token is supported for flash loans
        if token not in FLASH_LOAN_TOKENS:
            return FlashLoanQuote(
                token=token,
                symbol=get_symbol(token),
                amount=0,
                amount_human=amount_human,
                fee_amount=0,
                fee_human=Decimal(0),
                fee_bps=0,
                available_liquidity=0,
                is_available=False,
                reason=f"Token {get_symbol(token)} not supported for flash loans"
            )
        
        # Convert to wei
        decimals = get_decimals(token)
        amount = int(amount_human * Decimal(10 ** decimals))
        
        # Get available liquidity
        liquidity = self.get_available_liquidity(token)
        
        if liquidity < amount:
            return FlashLoanQuote(
                token=token,
                symbol=get_symbol(token),
                amount=amount,
                amount_human=amount_human,
                fee_amount=0,
                fee_human=Decimal(0),
                fee_bps=self.get_flash_loan_fee_bps(),
                available_liquidity=liquidity,
                is_available=False,
                reason=f"Insufficient liquidity: {liquidity} < {amount}"
            )
        
        # Calculate fee
        fee_bps = self.get_flash_loan_fee_bps()
        fee_amount, fee_human = self.calculate_fee(amount, token)
        
        return FlashLoanQuote(
            token=token,
            symbol=get_symbol(token),
            amount=amount,
            amount_human=amount_human,
            fee_amount=fee_amount,
            fee_human=fee_human,
            fee_bps=fee_bps,
            available_liquidity=liquidity,
            is_available=True,
        )
    
    def get_optimal_loan_token(
        self,
        amount_usd: Decimal,
        preferred_tokens: List[str] = None
    ) -> Optional[FlashLoanQuote]:
        """
        Find the optimal token for flash loan based on liquidity and fees
        For stablecoin arbitrage, prefer USDC or USDT
        """
        from bot.pairs import USDC_LEGACY, USDT, DAI, WMATIC
        
        if preferred_tokens is None:
            # Default preference order for stable-based arbitrage
            preferred_tokens = [USDC_LEGACY, USDT, DAI]
        
        best_quote = None
        
        for token in preferred_tokens:
            quote = self.quote_flash_loan(token, amount_usd)
            
            if quote.is_available:
                if best_quote is None or quote.fee_bps < best_quote.fee_bps:
                    best_quote = quote
        
        return best_quote
    
    def build_flash_loan_tx(
        self,
        receiver: str,
        token: str,
        amount: int,
        params: bytes,
        from_address: str,
        gas_price: int,
        nonce: int,
    ) -> dict:
        """
        Build a flash loan transaction (not signed)
        This calls flashLoanSimple for single-asset loans
        """
        tx = self.pool.functions.flashLoanSimple(
            Web3.to_checksum_address(receiver),
            Web3.to_checksum_address(token),
            amount,
            params,
            0,  # referralCode
        ).build_transaction({
            "from": Web3.to_checksum_address(from_address),
            "gas": 500000,  # Estimate, will be refined
            "gasPrice": gas_price,
            "nonce": nonce,
            "chainId": 137,  # Polygon
        })
        
        return tx
    
    def encode_arbitrage_params(
        self,
        dex_buy: str,
        dex_sell: str,
        path_buy: List[str],
        path_sell: List[str],
        min_profit: int,
    ) -> bytes:
        """
        Encode arbitrage parameters for the flash loan callback
        This will be decoded by the arbitrage contract
        """
        # Simple encoding - in production use proper ABI encoding
        from eth_abi import encode
        
        return encode(
            ['address', 'address', 'address[]', 'address[]', 'uint256'],
            [
                Web3.to_checksum_address(dex_buy),
                Web3.to_checksum_address(dex_sell),
                [Web3.to_checksum_address(a) for a in path_buy],
                [Web3.to_checksum_address(a) for a in path_sell],
                min_profit
            ]
        )


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def calculate_total_repayment(amount: int, fee_bps: int) -> int:
    """Calculate total amount to repay (principal + fee)"""
    fee = (amount * fee_bps) // 10000
    return amount + fee


def estimate_flash_loan_profit(
    loan_amount: Decimal,
    expected_return: Decimal,
    fee_bps: int = AAVE_FLASH_FEE_BPS,
) -> Tuple[Decimal, Decimal]:
    """
    Estimate profit from flash loan arbitrage
    Returns (gross_profit, net_profit_after_flash_fee)
    """
    flash_fee = loan_amount * Decimal(fee_bps) / Decimal(10000)
    gross_profit = expected_return - loan_amount
    net_profit = gross_profit - flash_fee
    
    return gross_profit, net_profit
