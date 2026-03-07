#!/bin/bash

echo "================================================"
echo "  Fixing Chatbot Service Dependencies"
echo "================================================"
echo ""

cd chatbot-service

# Remove old venv if it exists
if [ -d ".venv" ]; then
    echo "🗑️  Removing old virtual environment..."
    rm -rf .venv
fi

# Create fresh venv
echo "📦 Creating fresh virtual environment..."
python3 -m venv .venv

# Activate and install
echo "⬇️  Installing dependencies..."
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "================================================"
echo "  ✅ Chatbot Service Dependencies Fixed"
echo "================================================"
echo ""
echo "Now run: bash start_dev.sh"
