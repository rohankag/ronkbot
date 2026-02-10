#!/bin/bash

echo "🚀 Starting ronkbot..."

cd "$(dirname "$0")/.."

# Check which docker compose command is available
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

# Check if already running
if $COMPOSE_CMD ps | grep -q "Up"; then
    echo "✅ ronkbot is already running!"
    echo "🌐 n8n UI: http://localhost:5678"
    echo "📱 Test your bot on Telegram: @ronkbot"
    exit 0
fi

# Start containers
$COMPOSE_CMD up -d

# Wait a moment
sleep 3

# Check if started successfully
if curl -s http://localhost:5678/healthz > /dev/null 2>&1; then
    echo "✅ ronkbot is running!"
    echo "🌐 n8n UI: http://localhost:5678"
    echo "📱 Test your bot on Telegram: @ronkbot"
else
    echo "⏳ Starting up... check again in 10 seconds"
    echo "   Or view logs: $COMPOSE_CMD logs -f"
fi
