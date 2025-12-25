# bot/config.py

import os
from dotenv import load_dotenv
from pathlib import Path

# -----------------------------
# Load .env safely
# -----------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / "config" / ".env"

if not ENV_PATH.exists():
    raise RuntimeError(f".env file not found at {ENV_PATH}")

load_dotenv(ENV_PATH)

# -----------------------------
# RPC
# -----------------------------
RPC_WS_PRIMARY = os.getenv("RPC_WS_PRIMARY")
if not RPC_WS_PRIMARY:
    raise RuntimeError("RPC_WS_PRIMARY not set in .env")

# -----------------------------
# Wallet (Stage 4A)
# -----------------------------
PUBLIC_ADDRESS = os.getenv("PUBLIC_ADDRESS")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")  # loaded but NOT used yet

if not PUBLIC_ADDRESS:
    raise RuntimeError("PUBLIC_ADDRESS not set in .env")

# -----------------------------
# Safety thresholds
# -----------------------------
MAX_RPC_LATENCY = 1.0
MAX_BLOCK_LAG = 3

