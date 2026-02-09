#!/bin/bash

set -e

echo "🚀 Setting up ronku_bot..."
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Docker is installed
if ! command -v docker &> /dev/null; then
    echo "${RED}❌ Docker not found.${NC}"
    echo "   Please install Docker Desktop first:"
    echo "   https://www.docker.com/products/docker-desktop"
    exit 1
fi

# Check Docker Compose (supports both old and new syntax)
if ! docker compose version &> /dev/null && ! command -v docker-compose &> /dev/null; then
    echo "${RED}❌ Docker Compose not found.${NC}"
    echo "   Please install Docker Desktop or docker-compose plugin"
    exit 1
fi

# Set compose command (prefer new 'docker compose')
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

echo "${GREEN}✅ Docker found${NC}"

# Check if .env exists and has been edited
if [ ! -f .env ]; then
    echo "${RED}❌ .env file not found!${NC}"
    echo "   Please create it from .env.example:"
    echo "   cp .env.example .env"
    exit 1
fi

# Check if API keys have been set
if grep -q "your_telegram_bot_token_here" .env; then
    echo "${YELLOW}⚠️  Telegram bot token not set!${NC}"
    echo "   Please edit .env and add your Telegram bot token"
    echo "   Get it from @BotFather on Telegram"
    exit 1
fi

if grep -q "your_gemini_api_key_here" .env; then
    echo "${YELLOW}⚠️  Gemini API key not set!${NC}"
    echo "   Please edit .env and add your Gemini API key"
    echo "   Get it from https://ai.google.dev/"
    exit 1
fi

echo "${GREEN}✅ Configuration looks good${NC}"

# Create data directories
echo "📁 Creating directories..."
mkdir -p data/n8n data/sqlite
chmod 755 data data/n8n data/sqlite

# Pull n8n image
echo "⬇️  Pulling n8n image (this may take a few minutes)..."
$COMPOSE_CMD pull

# Start containers
echo "🚀 Starting n8n..."
$COMPOSE_CMD up -d

# Wait for n8n to be ready
echo "⏳ Waiting for n8n to start..."
attempt=1
max_attempts=30
while [ $attempt -le $max_attempts ]; do
    if curl -s http://localhost:5678/healthz > /dev/null 2>&1; then
        echo "${GREEN}✅ n8n is running!${NC}"
        break
    fi
    echo "   Attempt $attempt/$max_attempts..."
    sleep 2
    attempt=$((attempt + 1))
done

if [ $attempt -gt $max_attempts ]; then
    echo "${YELLOW}⚠️  n8n might still be starting.${NC}"
    echo "   Check status with: $COMPOSE_CMD logs -f"
fi

echo ""
echo "${GREEN}🎉 Setup complete!${NC}"
echo ""
echo "📱 Next steps:"
echo "   1. Open n8n: ${YELLOW}http://localhost:5678${NC}"
echo "   2. Login with your credentials (check .env file)"
echo "   3. Import workflows from n8n-workflows/ folder"
echo "   4. Configure Telegram credentials"
echo "   5. Test your bot on Telegram!"
echo ""
echo "🔧 Useful commands:"
echo "   ${YELLOW}$COMPOSE_CMD logs -f${NC}    # View logs"
echo "   ${YELLOW}$COMPOSE_CMD stop${NC}       # Stop bot"
echo "   ${YELLOW}$COMPOSE_CMD start${NC}      # Start bot"
echo "   ${YELLOW}./scripts/start.sh${NC}        # Quick start"
echo "   ${YELLOW}./scripts/backup.sh${NC}       # Backup workflows"
echo ""
echo "📖 Documentation:"
echo "   ${YELLOW}cat README.md${NC}             # Full guide"
echo "   ${YELLOW}cat docs/COMMANDS.md${NC}      # Bot commands"
echo ""
