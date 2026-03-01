# ronkbot on Docker Hub

[![Docker Pulls](https://img.shields.io/docker/pulls/rohankag/ronkbot)](https://hub.docker.com/r/rohankag/ronkbot)
[![Docker Image Size](https://img.shields.io/docker/image-size/rohankag/ronkbot/latest)](https://hub.docker.com/r/rohankag/ronkbot)

**ronkbot** — Personal AI assistant running locally. Telegram ↔ n8n ↔ Gemini.

All 7 n8n workflows (chat, commands, Gmail integration, writing style analyzer) are pre-loaded in the image.

---

## Quick Start

```bash
docker run -d \
  --name ronkbot \
  -p 5678:5678 \
  -v ~/.ronkbot/data:/home/node/.n8n \
  -e TELEGRAM_BOT_TOKEN=your_token \
  -e GEMINI_API_KEY=your_key \
  -e N8N_BASIC_AUTH_USER=admin \
  -e N8N_BASIC_AUTH_PASSWORD=changeme \
  rohankag/ronkbot:latest
```

Open <http://localhost:5678> to activate workflows.

---

## Docker Compose (Recommended)

```yaml
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
      # Optional — Gmail integration
      - GMAIL_ENABLED=${GMAIL_ENABLED:-false}
      - GMAIL_CLIENT_ID=${GMAIL_CLIENT_ID}
      - GMAIL_CLIENT_SECRET=${GMAIL_CLIENT_SECRET}
      - GMAIL_REDIRECT_URI=http://localhost:5678/gmail-auth
    volumes:
      - ./data:/home/node/.n8n
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | ✅ | Your Telegram bot token from @BotFather |
| `GEMINI_API_KEY` | ✅ | Google Gemini API key |
| `N8N_BASIC_AUTH_USER` | ✅ | n8n dashboard username |
| `N8N_BASIC_AUTH_PASSWORD` | ✅ | n8n dashboard password |
| `TELEGRAM_OWNER_USERNAME` | Recommended | Your Telegram username (security) |
| `GMAIL_ENABLED` | Optional | `true` to enable Gmail integration |
| `GMAIL_CLIENT_ID` | Optional | Google OAuth client ID |
| `GMAIL_CLIENT_SECRET` | Optional | Google OAuth client secret |
| `GMAIL_REDIRECT_URI` | Optional | Defaults to `http://localhost:5678/gmail-auth` |

---

## Image Tags

| Tag | Description |
|-----|-------------|
| `latest` | Latest stable release |
| `v1.0.0`, `v1.1.0`, ... | Specific version |

---

## What's Pre-loaded

All n8n workflows are baked into the image:

| Workflow | Purpose |
|---------|---------|
| `01-telegram-listener` | Receives Telegram messages |
| `02-gemini-chat` | AI conversation with memory |
| `03-command-handler` | Slash command routing |
| `04-gmail-authentication` | Gmail OAuth flow |
| `05-email-reader` | Read and cache emails |
| `06-email-sender` | AI-powered reply generation |
| `07-writing-style-analyzer` | Learn your writing style |

---

## Full Documentation

[github.com/rohankag/ronkbot](https://github.com/rohankag/ronkbot)
