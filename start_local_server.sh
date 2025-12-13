#!/bin/bash
# Script to start the local quiz solver server

echo "Starting local quiz solver server..."
echo "=================================="

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install/upgrade dependencies
echo "Installing dependencies..."
pip install -q -r requirements.txt

# Check if environment variables are set
echo ""
echo "Checking environment variables..."
if [ -z "$QUIZ_SECRET" ]; then
    echo "⚠️  WARNING: QUIZ_SECRET is not set"
    echo "   Set it with: export QUIZ_SECRET='your_secret'"
fi

if [ -z "$QUIZ_EMAIL" ]; then
    echo "⚠️  WARNING: QUIZ_EMAIL is not set"
    echo "   Set it with: export QUIZ_EMAIL='your_email'"
fi

if [ -z "$OPENROUTER_API_KEY" ]; then
    echo "⚠️  WARNING: OPENROUTER_API_KEY is not set"
    echo "   Set it with: export OPENROUTER_API_KEY='your_key'"
fi

if [ -z "$GOOGLE_API_KEY" ]; then
    echo "⚠️  WARNING: GOOGLE_API_KEY is not set"
    echo "   Set it with: export GOOGLE_API_KEY='your_key'"
    echo "   This is needed for audio transcription and image processing"
fi

echo ""
echo "Starting server on http://localhost:8000"
echo "Press Ctrl+C to stop the server"
echo "=================================="
echo ""

# Start the server
uvicorn main:app --reload --host 0.0.0.0 --port 8000


