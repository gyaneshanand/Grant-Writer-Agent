#!/bin/bash

# Grant Writer Agent - Check Server Status Script

echo "=== Grant Writer Agent Server Status ==="
echo ""

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

PORT="${PORT:-8000}"

# Check if PID file exists
if [ -f "logs/server.pid" ]; then
    PID=$(cat logs/server.pid)
    echo "PID file found: $PID"
    
    # Check if process is running
    if ps -p $PID > /dev/null; then
        echo "Status: ✓ Server is RUNNING"
        echo "PID: $PID"
        echo ""
        
        # Get process info
        echo "Process details:"
        ps -p $PID -o pid,ppid,cmd,%cpu,%mem,etime
        echo ""
        
        # Check if port is listening
        if lsof -i:$PORT > /dev/null 2>&1; then
            echo "Port Status: ✓ Port $PORT is listening"
        else
            echo "Port Status: ✗ Port $PORT is NOT listening"
        fi
    else
        echo "Status: ✗ Server is NOT RUNNING (PID file exists but process not found)"
    fi
else
    echo "PID file not found"
    
    # Check if something is running on the port
    PID=$(lsof -ti:$PORT 2>/dev/null)
    if [ ! -z "$PID" ]; then
        echo "Status: ⚠ Process found on port $PORT (PID: $PID) but no PID file"
        ps -p $PID -o pid,ppid,cmd,%cpu,%mem,etime
    else
        echo "Status: ✗ Server is NOT RUNNING"
    fi
fi

echo ""
echo "=== Recent Logs (last 10 lines) ==="
if [ -f "logs/server.log" ]; then
    tail -10 logs/server.log
else
    echo "No log file found"
fi

echo ""
echo "=== Health Check ==="
if curl -s http://localhost:$PORT/health > /dev/null 2>&1; then
    echo "✓ Server is responding to health checks"
    curl -s http://localhost:$PORT/health | python3 -m json.tool 2>/dev/null || curl -s http://localhost:$PORT/health
else
    echo "✗ Server is not responding to health checks"
fi
