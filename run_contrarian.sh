#!/bin/bash

# Run Phase 3: Contrarian Signal System
# Easy launcher script

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║      Phase 3: Contrarian Signal System - Launcher          ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${RED}❌ Virtual environment not found!${NC}"
    echo -e "${YELLOW}Please run: python3 -m venv venv${NC}"
    exit 1
fi

# Activate virtual environment
echo -e "${BLUE}Activating virtual environment...${NC}"
source venv/bin/activate

# Check if required packages are installed
echo -e "${BLUE}Checking dependencies...${NC}"
python3 -c "import rich" 2>/dev/null
if [ $? -ne 0 ]; then
    echo -e "${YELLOW}Installing required packages...${NC}"
    pip install rich aiolimiter
fi

# Check if Phase 2 database exists
if [ ! -f "data/analyzed_traders.db" ]; then
    echo -e "${RED}❌ Phase 2 database not found!${NC}"
    echo -e "${YELLOW}Please run Phase 2 analyzer first: python3 analyzer/main.py${NC}"
    exit 1
fi

# Check for bad traders
BAD_TRADER_COUNT=$(sqlite3 data/analyzed_traders.db "SELECT COUNT(*) FROM scored_traders WHERE score <= 5" 2>/dev/null)

if [ -z "$BAD_TRADER_COUNT" ] || [ "$BAD_TRADER_COUNT" -eq 0 ]; then
    echo -e "${RED}❌ No bad traders found in database!${NC}"
    echo -e "${YELLOW}Please ensure Phase 2 has analyzed traders.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Found $BAD_TRADER_COUNT bad traders in database${NC}"
echo ""

# Ask user what to do
echo -e "${BLUE}What would you like to do?${NC}"
echo "  1) Run continuous monitoring (recommended)"
echo "  2) Run single test cycle"
echo "  3) View recent signals from database"
echo ""
read -p "Enter choice [1-3]: " choice

case $choice in
    1)
        echo -e "${GREEN}Starting continuous monitoring...${NC}"
        echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
        echo ""
        sleep 2
        python3 contrarian/main.py
        ;;
    2)
        echo -e "${GREEN}Running test cycle...${NC}"
        echo ""
        python3 contrarian/test_contrarian.py
        ;;
    3)
        echo -e "${GREEN}Recent signals:${NC}"
        echo ""
        if [ -f "data/contrarian_signals.db" ]; then
            sqlite3 -header -column data/contrarian_signals.db \
                "SELECT datetime(timestamp, 'localtime') as time, coin, signal_direction, signal_strength, confidence_score
                 FROM contrarian_signals
                 ORDER BY timestamp DESC
                 LIMIT 20"
        else
            echo -e "${YELLOW}No signals database found. Run monitoring first.${NC}"
        fi
        ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac
