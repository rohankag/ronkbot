# ronku_bot 🤖

Your personal AI assistant running on Mac, accessible via Telegram. Built with n8n + Gemini API.

## Features

- 💬 **Natural Conversations** - Chat naturally with warm, conversational AI
- 🧠 **Memory** - Remembers facts about you across sessions
- 📊 **System Monitoring** - Check your Mac's status anytime
- 📁 **File Access** - Read files and list directories (safe, limited paths)
- ⚡ **Command Execution** - Run safe shell commands
- 🔒 **Privacy First** - Runs locally on your Mac, data stays private
- 🚀 **Portable** - Can move to any Mac with Docker

## Quick Start (5 minutes)

### 1. Prerequisites
- Docker Desktop installed on your Mac
- Telegram app on your phone
- Gemini API key from Google

### 2. Setup

```bash
# Navigate to the project
cd ~/ronku-bot

# Copy and edit environment file
cp .env.example .env
# Edit .env and add your API keys

# Run the installer
./scripts/install.sh
```

### 3. Create Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Enter name: `ronku_bot`
4. Enter username: `ronku_bot` (must be unique)
5. Copy the HTTP API token
6. Edit `.env` file: `TELEGRAM_BOT_TOKEN=your_token_here`
7. Restart: `docker-compose restart`

### 4. Access n8n UI

Open http://localhost:5678 in your browser

**Login credentials:**
- Username: `ronku` (from .env)
- Password: (from .env file, N8N_BASIC_AUTH_PASSWORD)

### 5. Import Workflows

1. In n8n, click "Workflows"
2. Import from file: `n8n-workflows/01-telegram-listener.json`
3. Import from file: `n8n-workflows/02-gemini-chat.json`
4. Import from file: `n8n-workflows/03-command-handler.json`
5. Activate all workflows

### 6. Test Your Bot

Send a message to **@ronku_bot** on Telegram!

Try:
- "Hello!"
- "Remember that I love pizza"
- "What do I love?"
- "/status"

## Bot Commands

### Chat Commands
Just message naturally - no slash commands needed!

Examples:
- "What's the weather like?" → AI response
- "Remind me to call mom tomorrow" → Sets reminder
- "Read me the file ~/Documents/notes.txt" → Reads file
- "How much disk space do I have?" → System info

### Slash Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/help` | Show available commands | `/help` |
| `/status` | Check Mac system status | `/status` |
| `/remember [fact]` | Save a fact to memory | `/remember I work at Google` |
| `/recall` | Show remembered facts | `/recall` |
| `/clear` | Clear conversation history | `/clear` |
| `/read [filepath]` | Read a text file | `/read ~/Documents/todo.txt` |
| `/list [directory]` | List directory contents | `/list ~/Projects` |
| `/exec [command]` | Run safe command | `/exec git status` |

## Architecture

```
Telegram App (Your Phone)
        ↓
Telegram Bot API
        ↓
n8n Workflow Engine (Docker)
        ↓
SQLite Database (Local)
        ↓
Gemini API (Google Cloud)
        ↓
AI Response
```

**Components:**
- **Telegram**: Messaging interface
- **n8n**: Workflow automation engine (runs in Docker)
- **SQLite**: Local database for conversation history
- **Gemini API**: AI brain (gemini-3-flash model)

## Daily Usage

### Start the Bot
```bash
./scripts/start.sh
```

Or manually:
```bash
docker-compose up -d
```

### Stop the Bot
```bash
docker-compose stop
```

### View Logs
```bash
docker-compose logs -f
```

### Backup Your Data
```bash
./scripts/backup.sh
```

## Configuration

Edit `.env` file to customize:

```bash
# Change AI model
GEMINI_MODEL=gemini-3-flash  # or gemini-3-pro

# Add more allowed directories
ALLOWED_DIRECTORIES=/Users/ronkuwonku/Documents,/Users/ronkuwonku/Projects,/Users/ronkuwonku/Desktop

# Change bot personality
BOT_PERSONALITY=conversational_warm  # or professional, technical, witty
```

## Moving to Another Mac

1. **Copy the entire folder** to new Mac
2. **Install Docker Desktop** on new Mac
3. **Run installer**:
   ```bash
   cd ~/ronku-bot
   ./scripts/install.sh
   ```
4. **Done!** All your conversations and memory come with it

## Troubleshooting

### Bot not responding?
1. Check if n8n is running: `docker-compose ps`
2. Check logs: `docker-compose logs -f`
3. Verify Telegram token in .env is correct
4. Restart: `docker-compose restart`

### Can't access n8n UI?
1. Make sure Docker is running
2. Check port 5678 is not in use: `lsof -i :5678`
3. Try: http://127.0.0.1:5678 instead of localhost

### Forgot n8n password?
1. Check `.env` file for N8N_BASIC_AUTH_PASSWORD
2. Or edit .env and restart: `docker-compose restart`

### Database issues?
1. Check permissions: `ls -la data/sqlite/`
2. Should be owned by your user
3. Try: `chmod 755 data data/sqlite`

## Security

- ✅ **Local only** - Runs on your Mac, no cloud dependency
- ✅ **Sandboxed** - Limited file/command access
- ✅ **Private** - Conversations stay in your SQLite database
- ✅ **Secure** - API keys in .env, never committed to git
- ✅ **Owner-only** - Only responds to @ronkuwonku

## Customization

### Change AI Personality

Edit system prompt in n8n Workflow 02:
1. Open n8n UI
2. Go to "Gemini Chat" workflow
3. Find "Function" node that builds context
4. Edit the systemPrompt variable

Example personalities:
- **Professional**: "You are a professional assistant..."
- **Fun**: "You are a witty, fun assistant..."
- **Technical**: "You are a technical expert..."

### Add New Commands

1. Open "Command Handler" workflow
2. Add new Switch case
3. Add action nodes
4. Save and activate

## Updates

To update n8n to latest version:
```bash
docker-compose pull
docker-compose up -d
```

## Support

- 📖 **Commands**: See `docs/COMMANDS.md`
- 🔧 **Setup Guide**: This README
- 💾 **Backup**: Run `./scripts/backup.sh`

## License

Personal use only. Built with ❤️ for ronkuwonku.

---

**Happy chatting!** 🤖💬
