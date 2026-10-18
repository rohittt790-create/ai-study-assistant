#!/usr/bin/env bash

# AI Study Assistant Startup Script
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "=========================================================="
echo "  🎓 Launching AI Study Assistant Web Application"
echo "=========================================================="

# Check for virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    ./venv/bin/pip install -r requirements.txt
fi

echo "Starting FastAPI server on http://localhost:8000..."
echo "Open your browser to: http://localhost:8000"
echo "Press Ctrl+C to stop."
echo "=========================================================="

exec ./venv/bin/uvicorn app:app --app-dir backend --host 0.0.0.0 --port 8000 --reload
