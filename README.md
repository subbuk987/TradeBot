# 🚀 Polygon Arbitrage Bot

## Production-Grade On-Chain Arbitrage System

**Target:** $4.50 → $150 in 10 days (~33x return)

⚠️ **IMPORTANT DISCLAIMER:** This is extremely aggressive. Crypto arbitrage is highly competitive. The system is designed for capital preservation, but profits are NOT guaranteed.

---

## 📁 Project Structure

```
TradeBot/
├── bot/
│   ├── __init__.py
│   ├── config.py              # Configuration & environment
│   ├── pairs.py               # Token & DEX registry
│   ├── flash_loan.py          # Aave V3 flash loan integration
│   ├── quote_engine.py        # Multi-DEX quote aggregation
│   ├── arbitrage_scanner.py   # Opportunity detection
│   ├── profit_calculator.py   # Profit calculation with all fees
│   ├── executor.py            # Trade execution engine
│   ├── main.py                # Main entry point
│   ├── rpc_health.py          # RPC health monitoring
│   └── filters/               # Safety filters
├── contracts/
│   └── FlashArbitrage.sol     # Flash loan arbitrage contract
├── config/
│   └── .env                   # Environment variables (KEEP SECRET!)
├── logs/                      # Trading logs
├── requirements.txt           # Python dependencies
└── README.md                  # This file
```

---

## 🛠️ Setup Instructions

### 1. Install Dependencies

```bash
cd TradeBot
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

Edit `config/.env`:
```
PRIVATE_KEY=your_private_key_here
PUBLIC_ADDRESS=your_wallet_address_here
RPC_WS_PRIMARY=https://polygon-rpc.com
```

**NEVER share your private key!**

### 3. Fund Your Wallet

You need:
- **USDC:** Your trading capital ($4.50)
- **MATIC:** For gas fees (~0.5 MATIC recommended)

---

## 🚀 Running the Bot

### Test Mode (Safe - No Execution)
```bash
python -m bot.main --mode test
```

### Scan Mode (Observe Opportunities)
```bash
python -m bot.main --mode scan --trade-size 4.0
```

### Simulate Mode (Scan + Simulate Trades)
```bash
python -m bot.main --mode simulate --trade-size 4.0
```

### Execute Mode (Real Trading)
```bash
# First, set DRY_RUN_MODE=False in config.py
python -m bot.main --mode execute --trade-size 4.0
```

---

## 📊 Arbitrage Strategies

### 1. Direct Arbitrage
- Buy on DEX A, sell on DEX B
- Example: Buy WMATIC on QuickSwap, sell on SushiSwap
- Requires price difference > fees + gas

### 2. Triangular Arbitrage
- A → B → C → A cycle
- Example: USDC → WMATIC → WETH → USDC
- Higher complexity, potentially higher profits

### 3. Flash Loan Arbitrage (Advanced)
- Borrow funds atomically
- Execute arbitrage
- Repay + profit in single transaction
- **Zero capital risk** (transaction reverts if unprofitable)
- Requires deployed contract

---

## 🔒 Safety Features

1. **Profit Validation:** No trade executes unless profitable after ALL fees
2. **Oracle Verification:** Prices checked against Chainlink
3. **Slippage Protection:** Min output enforced
4. **Gas Price Limits:** Won't execute if gas too expensive
5. **Simulation First:** Trades simulated before execution
6. **Circuit Breakers:** Auto-pause after consecutive failures
7. **Dry Run Mode:** Test everything without real trades

---

## 💰 Profit Requirements

For a trade to execute:
- Net profit ≥ $0.05
- Net profit ≥ 10 basis points (0.10%)

Costs included:
- DEX fees (0.30% per swap)
- Flash loan fee (0.05% if used)
- Gas fees
- Slippage

---

## 📈 Expected Performance

**Realistic expectations:**
- Most scans find 0 profitable opportunities
- When found, profits are typically $0.01 - $0.50
- Highly competitive market
- Success requires speed and low gas

**To achieve $150 in 10 days:**
- Need ~$14.56/day average
- With $4.50 capital, need many small profits
- Or use flash loans for larger trades

---

## 🧪 Testing

### Quick Test
```bash
python -m bot.main --mode test
```

### Check Wallet Balance
```python
from bot.executor import ExecutionEngine
from web3 import Web3

w3 = Web3(Web3.HTTPProvider("https://polygon-rpc.com"))
engine = ExecutionEngine(w3)

print(f"USDC: {engine.check_balance(USDC_NATIVE)}")
print(f"MATIC: {w3.eth.get_balance(PUBLIC_ADDRESS) / 1e18}")
```

---

## ⚠️ Risk Warnings

1. **Market Risk:** Prices can move against you
2. **Gas Risk:** High gas can eat profits
3. **Smart Contract Risk:** Bugs in contracts
4. **MEV Risk:** Bots can front-run you
5. **Liquidity Risk:** Large trades impact prices

**NEVER trade more than you can afford to lose!**

---

## 🔧 Troubleshooting

### "No profitable opportunities"
- Normal! Arbitrage is competitive
- Try different pairs
- Try different times (low activity = more opportunities)

### "Transaction reverted"
- Slippage protection worked
- Price moved before execution
- Increase slippage tolerance (carefully)

### "Insufficient gas"
- Add more MATIC to wallet
- Wait for lower gas prices

### "RPC errors"
- Try different RPC endpoint
- Check Polygon network status

---

## 📝 Logs

Logs are saved to `logs/bot_YYYYMMDD.log`

Monitor in real-time:
```bash
tail -f logs/bot_$(date +%Y%m%d).log
```

---

## 🚧 Future Improvements

1. **Multi-chain:** Arbitrum, Base, Optimism
2. **Flashbots:** MEV protection
3. **WebSocket:** Faster updates
4. **ML Models:** Predict profitable moments
5. **Dashboard:** Web UI for monitoring

---

## 📞 Support

This is research-grade software. Use at your own risk.

**Good luck! 🍀**
