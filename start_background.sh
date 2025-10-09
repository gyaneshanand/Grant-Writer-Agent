#!/bin/bash

# Grant Writer Agent - Background Server Startup Script for cPanel
# Runs the server in the background using nohup

echo "Starting Grant Writer Agent API in background..."

# Set Python path for cPanel
PYTHON_BIN="/home/tgpdev/python3.11/bin/python3.11"

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if Python exists
if [ ! -f "$PYTHON_BIN" ]; then
    echo "Error: Python not found at $PYTHON_BIN"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    $PYTHON_BIN -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install/update requirements
echo "Installing requirements..."
pip install -r requirements.txt

# Set the host and port for cPanel
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

# Create logs directory if it doesn't exist
mkdir -p logs

# Kill any existing process on the same port
OLD_PID=$(lsof -ti:$PORT)
if [ ! -z "$OLD_PID" ]; then
    echo "Killing existing process on port $PORT (PID: $OLD_PID)"
    kill -9 $OLD_PID 2>/dev/null
    sleep 2
fi

# Start the server in background with nohup
echo "Starting FastAPI server on http://$HOST:$PORT"
nohup uvicorn main:app --host $HOST --port $PORT > logs/server.log 2>&1 &

# Save the PID
SERVER_PID=$!
echo $SERVER_PID > logs/server.pid

echo "Server started with PID: $SERVER_PID"
echo "Logs are being written to: logs/server.log"
echo "PID saved to: logs/server.pid"
echo ""
echo "To view logs: tail -f logs/server.log"
echo "To stop server: ./stop_server.sh"
echo "API Documentation: http://$HOST:$PORT/docs"
