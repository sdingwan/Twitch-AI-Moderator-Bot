#!/bin/bash
# Simple installer for Twitch AI Moderator Bot

echo "🎤 Installing Twitch AI Moderator Bot..."

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required. Please install Python 3.8+ first."
    exit 1
fi

# Create virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install dependencies
echo "⬇️ Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "✅ Installation complete!"
echo ""
echo "Next steps:"
echo "1. Create .env file with your credentials"
echo "2. Run: python main.py --test-mic"
echo "3. Run: python main.py"
echo ""
echo "See README.md for configuration details." 