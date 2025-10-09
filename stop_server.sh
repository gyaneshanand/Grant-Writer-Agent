#!/bin/bash

# Grant Writer Agent - Stop Background Server Script

echo "Stopping Grant Writer Agent API..."

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if PID file exists
if [ -f "logs/server.pid" ]; then
    PID=$(cat logs/server.pid)
    
    # Check if process is running
    if ps -p $PID > /dev/null; then
        echo "Stopping server (PID: $PID)..."
        kill $PID
        
        # Wait for process to stop
        sleep 2
        
        # Force kill if still running
        if ps -p $PID > /dev/null; then
            echo "Force killing server..."
            kill -9 $PID
        fi
        
        echo "Server stopped successfully"
    else
        echo "Server is not running (PID: $PID not found)"
    fi
    
    # Remove PID file
    rm logs/server.pid
else
    # Try to find and kill by port
    PORT="${PORT:-8000}"
    PID=$(lsof -ti:$PORT)
    
    if [ ! -z "$PID" ]; then
        echo "Found process on port $PORT (PID: $PID)"
        echo "Stopping server..."
        kill -9 $PID
        echo "Server stopped successfully"
    else
        echo "No server process found"
    fi
fi
