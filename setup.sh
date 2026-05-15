#!/bin/bash
# Setup script for AI SQL Backend

set -e

echo "Setting up AI SQL Backend..."

# Check Python version
python_version=$(python --version 2>&1 | awk '{print $2}')
echo "Python version: $python_version"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate || . venv/Scripts/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Copy .env file if not exists
if [ ! -f ".env" ]; then
    echo "Copying .env.example to .env..."
    cp .env.example .env
    echo "Please update .env with your configuration"
fi

# Create logs directory
mkdir -p logs

echo "Setup complete!"
echo ""
echo "Next steps:"
echo "1. Update .env with your database configuration"
echo "2. Run: python main.py"
echo "3. Visit: http://localhost:8000/docs"
