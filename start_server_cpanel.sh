#!/bin/bash

# Grant Writer Agent API Startup Script for cPanel
# Optimized for cPanel hosting environment

echo "Starting Grant Writer Agent API on cPanel..."

# Set Python path for cPanel
PYTHON_BIN="/home/tgpdev/python3.11/bin/python3.11"
PIP_BIN="/home/tgpdev/python3.11/bin/pip3.11"

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if Python exists
if [ ! -f "$PYTHON_BIN" ]; then
    echo "Error: Python not found at $PYTHON_BIN"
    exit 1
fi

# Display Python version
echo "Using Python:"
$PYTHON_BIN --version

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    $PYTHON_BIN -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
$PYTHON_BIN -m pip install --upgrade pip

# Install/update requirements
echo "Installing requirements..."
pip install -r requirements.txt

# Check for environment variables
if [ -z "$OPENAI_API_KEY" ]; then
    echo "Warning: OPENAI_API_KEY environment variable not set"
    echo "Please set it with: export OPENAI_API_KEY=your_api_key"
    echo "Or create a .env file with: OPENAI_API_KEY=your_api_key"
fi

# Set the host and port for cPanel
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

# Start the API server
echo "Starting FastAPI server on http://$HOST:$PORT"
echo "API Documentation available at: http://$HOST:$PORT/docs"
echo "Alternative docs at: http://$HOST:$PORT/redoc"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Run uvicorn with the virtual environment's Python
uvicorn main:app --host $HOST --port $PORT --reload
