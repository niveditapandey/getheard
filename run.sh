#!/bin/bash
# GetHeard - Voice Interview Platform launcher
cd "$(dirname "$0")"
source venv/bin/activate
echo "Starting GetHeard at http://localhost:8000"
python -m uvicorn src.web.app:app --host 0.0.0.0 --port 8000 --reload
