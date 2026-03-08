# Gmail Setup Guide for ronkbot

Complete guide to connecting your Gmail account to ronkbot.

## Prerequisites

- ronkbot running locally (`ronkbot status` should show green)
- A Google account you want to connect
- About 10 minutes

---

## Step 1: Create a Google Cloud Project

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Click **New Project**
3. Name it `ronkbot` → click **Create**
4. Make sure the new project is selected in the top dropdown

---

## Step 2: Enable the Gmail API

1. Go to **APIs & Services → Library**
2. Search for **Gmail API**
3. Click it → click **Enable**

---

## Step 3: Create OAuth 2.0 Credentials

1. Go to **APIs & Services → Credentials**
2. Click **+ Create Credentials → OAuth client ID**
3. If prompted, configure the **OAuth consent screen** first:
   - User Type: **External**
   - App name: `ronkbot` (or anything you like)
   - Add your email as a test user
4. Back on the Credentials page:
   - Application type: **Web application**
   - Name: `ronkbot`
   - Authorized redirect URIs: `http://localhost:5678/gmail-auth`
5. Click **Create**
6. Copy the **Client ID** and **Client Secret**

---

## Step 4: Add Credentials to .env

Open your `.env` file (in `~/.ronkbot/`) and fill in:

```bash
GMAIL_ENABLED=true
GMAIL_CLIENT_ID=your-client-id-here.apps.googleusercontent.com
GMAIL_CLIENT_SECRET=GOCSPX-your-secret-here
GMAIL_REDIRECT_URI=http://localhost:5678/gmail-auth
```

Restart ronkbot after editing:

```bash
ronkbot restart
```

---

## Step 5: Authorize Gmail Access

Send this command to your bot on Telegram:

```
/email auth
```

The bot will reply with an authorization link. Open it in your browser, sign in with Google, and grant the requested permissions.

You'll see: **✅ ronkbot is now connected to Gmail!**

---

## Step 6: Test the Connection

```
/email check
```

You should see a list of your recent unread emails.

---

## Available Email Commands

| Command | Description |
|---------|-------------|
| `/email auth` | Connect your Gmail account |
| `/email check` | Check unread emails (last 10) |
| `/email read [id]` | Read a specific email |
| `/email reply [id]` | Generate 3 AI reply options |
| `/email send` | Compose a new email |
| `/email search [query]` | Search emails |
| `/email analyze` | Analyze your writing style |

---

## Troubleshooting

**"No Gmail token found"**
→ Run `/email auth` first.

**Token expired**
→ Tokens refresh automatically. If issues persist, re-run `/email auth`.

**"redirect_uri_mismatch"**
→ Ensure `GMAIL_REDIRECT_URI` in `.env` exactly matches what you set in Google Cloud Console.

**Emails not showing**
→ Check the Gmail API is enabled and you're signed into the right Google account.

---

## Privacy Notes

- 🔒 OAuth tokens are stored in your **local SQLite database** — not in the cloud
- 📧 Email content is cached locally and never sent to third parties (only to Gemini API for AI features)
- 🔑 You control all permissions — scope is `gmail.modify` (read, send, label — no delete)
- 🛡️ Only your Telegram username can trigger email commands
