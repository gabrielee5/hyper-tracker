#!/bin/bash

# Hyperliquid Tracker - Quick Start Script

echo "======================================"
echo "Hyperliquid Trader Address Tracker"
echo "======================================"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install/update dependencies
echo "Installing dependencies..."
pip install -q -r requirements.txt

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "Please edit .env to configure your settings."
    exit 1
fi

# Create necessary directories
mkdir -p data logs

# Run the tracker
echo ""
echo "Starting tracker..."
echo "Dashboard will be available at: http://localhost:5000"
echo "Press Ctrl+C to stop"
echo ""

cd src && python main.py
