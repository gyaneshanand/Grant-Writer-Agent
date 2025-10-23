#!/bin/bash

# Grant Writer Agent - Background Server with Multiple Workers
# Optimized for handling parallel API calls

echo "Starting Grant Writer Agent API with multiple workers..."

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

# Number of worker processes (adjust based on CPU cores)
# Rule of thumb: (2 x CPU cores) + 1
# For 2 cores: 5 workers
# For 4 cores: 9 workers
WORKERS="${WORKERS:-10}"

# Create logs directory if it doesn't exist
mkdir -p logs

# Kill any existing process on the same port
OLD_PID=$(lsof -ti:$PORT)
if [ ! -z "$OLD_PID" ]; then
    echo "Killing existing process on port $PORT (PID: $OLD_PID)"
    kill -9 $OLD_PID 2>/dev/null
    sleep 2
fi

# Start the server in background with nohup and multiple workers
echo "Starting FastAPI server with $WORKERS workers on http://$HOST:$PORT"
echo "Estimated capacity: ~$((WORKERS * 100)) concurrent requests"
nohup uvicorn main:app \
    --host $HOST \
    --port $PORT \
    --workers $WORKERS \
    --limit-concurrency 1000 \
    --timeout-keep-alive 30 \
    --log-level info \
    > logs/server.log 2>&1 &

# Save the PID
SERVER_PID=$!
echo $SERVER_PID > logs/server.pid

echo ""
echo "✓ Server started with PID: $SERVER_PID"
echo "✓ Workers: $WORKERS"
echo "✓ Max concurrent connections: 1000"
echo "✓ Logs: logs/server.log"
echo "✓ PID file: logs/server.pid"
echo ""
echo "Commands:"
echo "  View logs: tail -f logs/server.log"
echo "  Stop server: ./stop_server.sh"
echo "  Check status: ./server_status.sh"
echo ""
echo "API Documentation: http://$HOST:$PORT/docs"
