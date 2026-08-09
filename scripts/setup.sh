#!/bin/bash
echo "============================================"
echo " Social Media Bot - Setup Script"
echo "============================================"
echo ""

if [ ! -f .env ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo ""
    echo "[!] IMPORTANT: Edit the .env file with your API keys before starting!"
    echo "    Run: nano .env"
    echo ""
fi

echo "To run the project:"
echo "  docker-compose up"
echo ""
echo "After starting, check: http://localhost:8000/health"
