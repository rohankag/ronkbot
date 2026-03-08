# 🌐 Ngrok Setup Guide

Telegram bots need a **public HTTPS URL** to receive messages. Since ronkbot runs on your local machine, you need a tunnel — [ngrok](https://ngrok.com/) creates one.

## 1. Install ngrok

**Mac (Homebrew):**

```bash
brew install ngrok
```

**Other platforms:** Download from [ngrok.com/download](https://ngrok.com/download)

## 2. Create a free account

1. Sign up at [dashboard.ngrok.com](https://dashboard.ngrok.com/signup)
2. Copy your auth token from the dashboard
3. Add it to ngrok:

```bash
ngrok config add-authtoken YOUR_AUTH_TOKEN
```

## 3. Claim a free static domain

Free accounts get **one static domain** (so your URL doesn't change on restart):

1. Go to [dashboard.ngrok.com/domains](https://dashboard.ngrok.com/domains)
2. Click **"Create Domain"** — you'll get something like `your-name-xyz.ngrok-free.app`

## 4. Configure ronkbot

Add your domain to `.env`:

```bash
NGROK_URL=https://your-name-xyz.ngrok-free.app
NGROK_DOMAIN=your-name-xyz.ngrok-free.app
```

## 5. Start the tunnel

```bash
ngrok http 5678 --domain=your-name-xyz.ngrok-free.app
```

> **Tip:** The `scripts/start-ronkbot.sh` script starts ngrok automatically if `NGROK_DOMAIN` is set in your `.env`.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Bot not receiving messages | Check tunnel is running: `curl https://your-domain.ngrok-free.app/healthz` |
| "Tunnel session expired" | Free plan sessions expire after ~2 hours of inactivity; restart ngrok |
| "Too many connections" | Free plan is limited to 40 connections/minute; this is fine for personal use |
