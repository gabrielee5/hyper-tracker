#!/bin/bash
# Quick start script for Hyperliquid Trader Analyzer

set -e

echo "================================"
echo "Hyperliquid Trader Analyzer"
echo "Phase 2 - Statistical Analysis"
echo "================================"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Virtual environment not found. Creating..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install/upgrade dependencies
echo "Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

echo ""
echo "Starting analyzer..."
echo ""

# Run analyzer
python main.py "$@"
