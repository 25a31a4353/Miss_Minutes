#!/bin/bash
# ==============================================================================
#  MISS MINUTES & JARVIS AI ASSISTANT - 1-CLICK SETUP SCRIPT (LINUX / MACOS)
#  Phase 8: Production Consolidation & Integration
# ==============================================================================

set -e

echo ""
echo "=================================================================="
echo "  🕒 WELCOME TO MISS MINUTES & JARVIS AI ASSISTANT SETUP 🕒       "
echo "=================================================================="
echo ""

# 1. Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.10+ and re-run."
    exit 1
fi

echo "✅ Python $(python3 --version) detected."

# 2. Setup Virtual Environment
if [ ! -d ".venv" ]; then
    echo "📦 Creating isolated Python environment (.venv)..."
    python3 -m venv .venv
else
    echo "✅ Existing virtual environment found."
fi

echo "📦 Activating environment..."
source .venv/bin/activate

# 3. Upgrade pip and install requirements
echo "⬇️  Installing required production packages..."
pip install --upgrade pip
pip install -r requirements.txt

# 4. Run automated self-diagnostics
echo ""
echo "🔍 Running self-diagnostics..."
python main.py --diagnostics

echo ""
echo "=================================================================="
echo "  🎉 SETUP COMPLETED SUCCESSFULLY!                                "
echo "=================================================================="
echo ""
echo "How to launch:"
echo "  1. Desktop / CLI:    python main.py"
echo "  2. Diagnostics:      python main.py --diagnostics"
echo "  3. Jarvis Dev Mode:  python main.py --jarvis"
echo ""
