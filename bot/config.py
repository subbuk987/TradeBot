# bot/config.py
"""
Production-Grade Arbitrage Configuration
Target: $4.50 → $150 in 10 days via flash loan arbitrage
"""

import os
from dotenv import load_dotenv
from pathlib import Path
from decimal import Decimal

# -----------------------------
# Load .env safely
# -----------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / "config" / ".env"

if not ENV_PATH.exists():
    raise RuntimeError(f".env file not found at {ENV_PATH}")

load_dotenv(ENV_PATH)

# -----------------------------
# Chain Configuration
# -----------------------------
CHAIN_ID = 137  # Polygon PoS
CHAIN_NAME = "polygon"

# -----------------------------
# RPC Configuration (Multiple for redundancy)
# -----------------------------
RPC_ENDPOINTS = [
    os.getenv("RPC_WS_PRIMARY", "https://polygon-rpc.com"),
    "https://rpc-mainnet.matic.quiknode.pro",
    "https://polygon-mainnet.g.alchemy.com/v2/demo",
    "https://rpc.ankr.com/polygon",
]

RPC_WS_PRIMARY = os.getenv("RPC_WS_PRIMARY")
if not RPC_WS_PRIMARY:
    raise RuntimeError("RPC_WS_PRIMARY not set in .env")

# -----------------------------
# Wallet Configuration
# -----------------------------
PUBLIC_ADDRESS = os.getenv("PUBLIC_ADDRESS")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")

if not PUBLIC_ADDRESS:
    raise RuntimeError("PUBLIC_ADDRESS not set in .env")
if not PRIVATE_KEY:
    raise RuntimeError("PRIVATE_KEY not set in .env")

# -----------------------------
# Capital & Target Configuration
# -----------------------------
INITIAL_CAPITAL_USD = Decimal("4.50")
TARGET_CAPITAL_USD = Decimal("150.00")
TARGET_DAYS = 10
DAILY_TARGET_MULTIPLIER = Decimal("1.40")  # ~40% daily to reach 33x in 10 days

# -----------------------------
# Flash Loan Configuration (Aave V3 on Polygon)
# -----------------------------
AAVE_POOL_ADDRESS = "0x794a61358D6845594F94dc1DB02A252b5b4814aD"  # Aave V3 Pool
AAVE_FLASH_LOAN_FEE_BPS = 5  # 0.05% flash loan fee

# Maximum flash loan sizes (conservative to ensure liquidity)
MAX_FLASH_LOAN_USD = Decimal("50000")  # Start conservative
MIN_FLASH_LOAN_USD = Decimal("100")    # Minimum viable trade

# -----------------------------
# Trading Parameters
# -----------------------------
# Profit thresholds (aggressive for high returns)
MIN_PROFIT_USD = Decimal("0.05")       # Minimum $0.05 profit per trade
MIN_PROFIT_BPS = 10                     # Minimum 0.10% profit after all fees
TARGET_PROFIT_BPS = 30                  # Target 0.30% profit per trade

# Slippage protection
MAX_SLIPPAGE_BPS = 50                   # 0.50% max slippage
DEFAULT_SLIPPAGE_BPS = 30               # 0.30% default

# Price impact limits
MAX_PRICE_IMPACT_BPS = 100              # 1.00% max price impact

# -----------------------------
# Gas Configuration
# -----------------------------
GAS_LIMIT_SWAP = 200_000
GAS_LIMIT_FLASH_LOAN = 500_000
GAS_LIMIT_TRIANGULAR = 600_000
GAS_LIMIT_APPROVAL = 60_000

# Gas price limits (in Gwei)
MAX_GAS_PRICE_GWEI = 500
TARGET_GAS_PRICE_GWEI = 50
MIN_GAS_PRICE_GWEI = 30

# -----------------------------
# DEX Fee Configuration (in BPS = basis points)
# -----------------------------
DEX_FEES = {
    "quickswap": 30,      # 0.30%
    "sushiswap": 30,      # 0.30%
    "uniswap_v3_500": 5,  # 0.05%
    "uniswap_v3_3000": 30, # 0.30%
    "uniswap_v3_10000": 100, # 1.00%
    "balancer": 10,       # Variable, estimate 0.10%
    "curve": 4,           # 0.04%
    "apeswap": 20,        # 0.20%
    "dfyn": 30,           # 0.30%
    "meshswap": 30,       # 0.30%
}

# -----------------------------
# Safety Thresholds
# -----------------------------
MAX_RPC_LATENCY = 2.0          # seconds
MAX_BLOCK_LAG = 5              # blocks
MAX_ORACLE_DEVIATION_PCT = 5.0  # 5% max deviation from oracle
MAX_DEX_SPREAD_PCT = 3.0        # 3% max spread between DEXs

# Circuit breakers
MAX_CONSECUTIVE_FAILURES = 5
MAX_DAILY_LOSS_USD = Decimal("1.00")  # Stop if losing more than $1/day
MAX_TRADES_PER_HOUR = 100

# -----------------------------
# Scan Configuration
# -----------------------------
SCAN_INTERVAL_SECONDS = 1.0     # Check for opportunities every second
OPPORTUNITY_TIMEOUT_SECONDS = 3  # Max time from detection to execution

# -----------------------------
# Logging & Monitoring
# -----------------------------
LOG_LEVEL = "INFO"
LOG_ALL_QUOTES = False          # Set True for debugging
LOG_ALL_OPPORTUNITIES = True
SAVE_TRADE_HISTORY = True

# -----------------------------
# Deployment Mode
# -----------------------------
DRY_RUN_MODE = True             # Set False for real execution
SIMULATION_MODE = True          # Use callStatic before real tx

