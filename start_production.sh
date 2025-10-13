#!/bin/bash

# Grant Writer Agent - Production Server with Gunicorn
# Best for high-traffic production environments

echo "Starting Grant Writer Agent API with Gunicorn (Production Mode)..."

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

# Install/update requirements including gunicorn
echo "Installing requirements..."
pip install -r requirements.txt
pip install gunicorn

# Create logs directory if it doesn't exist
mkdir -p logs

# Set the port
PORT="${PORT:-8000}"

# Kill any existing process on the same port
OLD_PID=$(lsof -ti:$PORT)
if [ ! -z "$OLD_PID" ]; then
    echo "Killing existing process on port $PORT (PID: $OLD_PID)"
    kill -9 $OLD_PID 2>/dev/null
    sleep 2
fi

# Start with gunicorn in background
echo "Starting Gunicorn server..."
nohup gunicorn main:app -c gunicorn.conf.py > logs/gunicorn_startup.log 2>&1 &

# Save the PID
SERVER_PID=$!
echo $SERVER_PID > logs/server.pid

sleep 2

echo ""
echo "✓ Server started with PID: $SERVER_PID"
echo "✓ Configuration: gunicorn.conf.py"
echo "✓ Access logs: logs/access.log"
echo "✓ Error logs: logs/error.log"
echo ""
echo "Commands:"
echo "  View access logs: tail -f logs/access.log"
echo "  View error logs: tail -f logs/error.log"
echo "  Stop server: ./stop_server.sh"
echo "  Check status: ./server_status.sh"
echo ""
echo "API Documentation: http://localhost:$PORT/docs"
