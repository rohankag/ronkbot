# Docker Hub Distribution

## Quick Start

### Option 1: Docker Run

```bash
docker run -d \
  --name ronkbot \
  -p 5678:5678 \
  -v ~/.ronkbot/data:/home/node/.n8n \
  -v ~/.ronkbot/workflows:/app/workflows \
  -e TELEGRAM_BOT_TOKEN=your_token \
  -e GEMINI_API_KEY=your_key \
  rohankag/ronkbot:latest
```

### Option 2: Docker Compose

```yaml
version: '3.8'

services:
  ronkbot:
    image: rohankag/ronkbot:latest
    container_name: ronkbot
    restart: unless-stopped
    ports:
      - "5678:5678"
    environment:
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - N8N_BASIC_AUTH_USER=admin
      - N8N_BASIC_AUTH_PASSWORD=${N8N_PASSWORD}
    volumes:
      - ./data:/home/node/.n8n
      - ./workflows:/app/workflows
```

## Tags

- `latest` - Stable release
- `v1.0.0` - Version 1.0.0
- `dev` - Development build

## Configuration

See full documentation at: https://github.com/rohankag/ronkbot

## Support

- GitHub Issues: https://github.com/rohankag/ronkbot/issues
- Documentation: https://github.com/rohankag/ronkbot/wiki
