#!/bin/bash
# ===========================================
# Polygon Arbitrage Bot - Start Script
# ===========================================

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo ""
echo "=============================================="
echo "🚀 POLYGON ARBITRAGE BOT"
echo "=============================================="
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Check if dependencies are installed
if ! python -c "import web3" 2>/dev/null; then
    echo -e "${YELLOW}Installing dependencies...${NC}"
    pip install -r requirements.txt
fi

# Check if .env exists
if [ ! -f "config/.env" ]; then
    echo -e "${RED}ERROR: config/.env not found!${NC}"
    echo "Copy config/.env.example to config/.env and configure it."
    exit 1
fi

# Parse arguments
MODE=${1:-scan}
TRADE_SIZE=${2:-4.0}

echo -e "Mode: ${GREEN}$MODE${NC}"
echo -e "Trade Size: ${GREEN}\$$TRADE_SIZE${NC}"
echo ""

# Run the bot
python -m bot.main --mode $MODE --trade-size $TRADE_SIZE
