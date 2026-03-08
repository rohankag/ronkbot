# 🤖 ronkbot

[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)](https://hub.docker.com/r/rohankag/ronkbot)
[![n8n](https://img.shields.io/badge/n8n-%23FF6D5A.svg?style=for-the-badge&logo=n8n&logoColor=white)](https://n8n.io/)
[![Google Gemini](https://img.shields.io/badge/Gemini-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev/)
[![Telegram](https://img.shields.io/badge/Telegram-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white)](https://telegram.org/)
[![Docker Pulls](https://img.shields.io/docker/pulls/rohankag/ronkbot?style=for-the-badge)](https://hub.docker.com/r/rohankag/ronkbot)
[![License](https://img.shields.io/badge/license-MIT-blue?style=for-the-badge)](LICENSE)

**ronkbot** - A personal AI assistant that runs on your Mac and responds to Telegram messages. Built with **n8n** workflows and powered by **Google Gemini API**.

> 💡 **Privacy First**: Your data stays local. Conversations are stored in a local SQLite database, not in the cloud.

---

## ✨ Features

- 💬 **Natural Conversations** - Chat naturally with warm, conversational AI
- 🧠 **Persistent Memory** - Remembers facts about you across sessions
- 📊 **System Monitoring** - Check your Mac's status (disk, memory, uptime)
- 📁 **File Operations** - Read files and list directories (safely restricted)
- ⚡ **Command Execution** - Run whitelisted safe shell commands
- 📧 **Gmail Integration** - Check, read, search, and reply to emails with AI
- 🤖 **AI Email Replies** - Generates Formal / Casual / Brief reply options
- ✍️ **Writing Style Learning** - Analyzes your sent emails to match your voice
- 🔒 **Privacy Focused** - All data stays local on your machine
- 🚀 **Portable** - Docker-based, runs on any system
- 🛠️ **Customizable** - Easy to extend with new commands and features

---

## 🏗️ Architecture

```
┌─────────────────┐
│ Telegram App    │
│ (Your Phone)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Telegram Bot API│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ n8n Workflows   │
│ (Docker)        │
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌────────┐ ┌─────────────┐
│ SQLite │ │ Gemini API  │
│ (Local)│ │ (Google)    │
└────────┘ └─────────────┘
```

---

## 🚀 Quick Install (One Command)

```bash
curl -fsSL https://raw.githubusercontent.com/rohankag/ronkbot/main/install.sh | bash
```

This interactive wizard will guide you through setup in 5-10 minutes.

---

### 🔒 Security Note

The installer uses `curl | bash` for convenience. To verify the script first:

```bash
# Download and inspect
curl -fsSL https://raw.githubusercontent.com/rohankag/ronkbot/main/install.sh -o install.sh
less install.sh

# Then run
bash install.sh
```

---

### Alternative Installation Methods

**Homebrew (Mac):**

```bash
brew tap rohankag/ronkbot
brew install ronkbot
ronkbot config
```

**Docker Hub:**

```bash
docker pull rohankag/ronkbot:latest
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

**Manual:**

```bash
git clone https://github.com/rohankag/ronkbot.git ~/.ronkbot
cd ~/.ronkbot
./install.sh
```

---

## 📖 What the Installer Does

The interactive wizard will:

1. ✅ Check prerequisites (Docker, Git)
2. 🤖 Guide you through Telegram bot creation
3. 🔑 Help you get Gemini API key  
4. 📧 (Optional) Setup Gmail OAuth
5. 🔐 Generate secure configuration
6. 🚀 Start ronkbot

### CLI Commands Available

After installation, use the `ronkbot` command:

```bash
ronkbot start      # Start the bot
ronkbot stop       # Stop the bot  
ronkbot status     # Check if running
ronkbot logs       # View logs
ronkbot config     # Reconfigure settings
ronkbot update     # Update to latest
ronkbot backup     # Backup data
ronkbot help       # Show all commands
```

### Manual Setup (If You Prefer)

For manual configuration, follow the steps below or refer to `docs/COMMANDS.md` for the full command reference.

This will:

- Pull the n8n Docker image
- Start the containers
- Set up the local database

### 4. Configure n8n

1. Open <http://localhost:5678> in your browser
2. Login with credentials from your `.env` file
3. Add credentials:
   - **Telegram API**: Add your bot token
   - **Google Gemini API**: Add your Gemini API key
4. Import the workflows from `n8n-workflows/` folder
5. Activate all workflows

### 5. Start Chatting

Send a message to your bot on Telegram:

```
Hello!
```

Try the commands:

- `/help` - Show available commands
- `/status` - Check system status
- `/remember I love pizza` - Save a fact
- `/recall` - Show remembered facts

---

## 📚 Available Commands

### Natural Chat

Just message the bot naturally - no commands needed!

Examples:

- "What's the weather like?"
- "Remind me to call mom tomorrow"
- "How much disk space do I have?"

### Slash Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/help` | Show all commands | `/help` |
| `/status` | System status (disk, memory) | `/status` |
| `/remember [fact]` | Save fact to memory | `/remember My birthday is June 15` |
| `/recall` | Show all remembered facts | `/recall` |
| `/clear` | Clear conversation history | `/clear` |
| `/read [path]` | Read a text file | `/read ~/Documents/notes.txt` |
| `/list [dir]` | List directory | `/list ~/Projects` |
| `/exec [cmd]` | Run safe command | `/exec git status` |

---

## ⚙️ Configuration

Edit `.env` file to customize:

```bash
# Bot Configuration
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_BOT_NAME=your_bot_name
TELEGRAM_OWNER_USERNAME=your_telegram_username

# AI Configuration
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-3-flash  # or gemini-3-pro

# Security
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=strong_password_here

# System Access (comma-separated paths)
ALLOWED_DIRECTORIES=/Users/yourname/Documents,/Users/yourname/Projects

# Allowed shell commands (comma-separated)
ALLOWED_COMMANDS=df,du,git,ls,cat,ps,top,whoami,pwd,date,cal
```

---

## 🔒 Security

- ✅ **API Keys**: Stored in `.env` (never committed to git)
- ✅ **Local Database**: SQLite database stays on your machine
- ✅ **Sandboxed**: Restricted file system and command access
- ✅ **Owner Only**: Bot only responds to configured username
- ✅ **Safe Commands**: Only whitelisted commands can be executed

---

## 🛠️ Development

### Project Structure

```
ronkbot/
├── docker-compose.yml      # Docker configuration
├── .env                    # Your secrets (gitignored)
├── .env.example            # Template for new users
├── README.md               # This file
├── n8n-workflows/          # Workflow JSON files
│   ├── 01-telegram-listener.json
│   ├── 02-gemini-chat.json
│   ├── 03-command-handler.json
│   ├── 04-gmail-authentication.json
│   ├── 05-email-reader.json
│   └── 06-email-sender.json
├── scripts/                # Helper scripts
│   ├── install.sh
│   ├── start.sh
│   └── backup.sh
├── tests/                  # Automated tests
│   ├── run-tests.sh
│   ├── test-json-valid.sh
│   ├── test-shellcheck.sh
│   └── test-docker-build.sh
├── .github/
│   └── workflows/
│       └── ci.yml          # GitHub Actions CI
├── data/                   # Persistent data (gitignored)
│   └── sqlite/
└── docs/
    └── COMMANDS.md         # Detailed command reference
```

### Adding New Features

1. Create a new workflow in n8n
2. Export it to `n8n-workflows/`
3. Update documentation
4. Commit and push

### Creating New Commands

1. Open `n8n-workflows/03-command-handler.json`
2. Add a new case to the Switch node
3. Add action nodes for your command
4. Save and activate the workflow

---

## 🔄 Backup & Restore

### Backup

```bash
./scripts/backup.sh
```

This creates a timestamped backup in `backups/` folder.

### Restore

```bash
# Copy backup files back
cp backups/YYYYMMDD_HHMMSS/.env .
cp backups/YYYYMMDD_HHMMSS/ronkbot.db data/sqlite/
cp -r backups/YYYYMMDD_HHMMSS/n8n-workflows/* n8n-workflows/

# Restart
docker-compose restart
```

---

## 🐛 Troubleshooting

### Bot Not Responding?

1. Check if n8n is running:

   ```bash
   docker-compose ps
   ```

2. Check logs:

   ```bash
   docker-compose logs -f
   ```

3. Verify Telegram token is correct in `.env`

4. Ensure workflows are activated in n8n UI

### Database Issues?

```bash
# Check permissions
ls -la data/sqlite/

# Fix permissions
chmod 755 data data/sqlite
```

### Port Already in Use?

```bash
# Find what's using port 5678
lsof -i :5678

# Change port in docker-compose.yml if needed
```

---

## 🌟 Advanced Features

### Custom AI Personality

Edit the system prompt in workflow `02-gemini-chat.json`:

```javascript
const systemPrompt = `You are [YOUR BOT NAME], a [PERSONALITY] AI assistant.

Your personality: [DESCRIBE PERSONALITY]

You can help with: [LIST CAPABILITIES]
`;
```

### Adding WhatsApp Support

You can extend this to support WhatsApp Business API:

1. Apply for WhatsApp Business API
2. Add WhatsApp trigger node
3. Reuse the same AI and command handlers

### Integration with Other Services

n8n supports 400+ integrations. You can easily add:

- Gmail (read/send emails)
- Google Calendar (check/create events)
- GitHub (repository operations)
- Slack notifications
- And more!

---

## 📖 Documentation

- [Command Reference](docs/COMMANDS.md) - Detailed command documentation
- [n8n Documentation](https://docs.n8n.io/) - Learn more about n8n
- [Gemini API Docs](https://ai.google.dev/docs) - Gemini API reference
- [Telegram Bot API](https://core.telegram.org/bots/api) - Telegram bot documentation

---

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Ensure no secrets are committed
5. Submit a pull request

---

## 📝 License

MIT License - feel free to use this for personal or commercial projects.

---

## 📱 Remote Control from iPhone

Control ronkbot from your iPhone via Telegram:

| Command | What it does |
|---------|-------------|
| `/system status` | Check if bot is running |
| `/system restart` | Restart the container (~30s downtime) |
| `/system stop` | Stop the bot |
| `/system wake` | Check Mac power/sleep status |

> **Owner only** — commands are restricted to `TELEGRAM_OWNER_USERNAME`.

### Starting ronkbot from iPhone

When the bot is stopped, start it with one tap using a macOS Shortcut:

```bash
bash scripts/create-shortcut.sh
```

This creates a **Start ronkbot** Shortcut that syncs to your iPhone via iCloud. Long-press it → **Add to Home Screen** for one-tap startup.

### Lid Closed Operation

By default, closing your MacBook lid puts it to sleep (pausing ronkbot). To keep it awake:

1. **Plug in** your Mac to power
2. Install [**Amphetamine**](https://apps.apple.com/us/app/amphetamine/id937984704) (free, Mac App Store)
3. Enable "Keep Awake" → check **Closed Lid Support**

Run `/system wake` from your iPhone anytime to check the current sleep status.

---

## 💖 Acknowledgments

- [n8n](https://n8n.io/) - Workflow automation platform
- [Google Gemini](https://ai.google.dev/) - AI model
- [Telegram](https://telegram.org/) - Messaging platform
- [Docker](https://www.docker.com/) - Containerization

---

**Enjoy your personal AI assistant!** 🤖💬

If you found this useful, please ⭐ star the repository!
