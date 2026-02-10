# ronkbot Commands Reference

Complete guide to all commands available in ronkbot.

## 💬 Natural Chat

You don't need commands for most things! Just chat naturally:

### Examples

**General Questions:**
- "What's the capital of France?"
- "Explain quantum computing simply"
- "What time is it in Tokyo?"

**Personal Assistant:**
- "Remind me to call mom at 5pm"
- "Add milk to my shopping list"
- "What's on my calendar today?"

**System Information:**
- "How much disk space do I have?"
- "Show me my recent git commits"
- "Check if my website is up"

**File Operations:**
- "Read me the todo.txt file"
- "List files in my Projects folder"
- "Show me the first 10 lines of log.txt"

**Learning & Memory:**
- "Remember that my wifi password is xyz123"
- "What did I ask you to remember?"
- "I work at Google as an engineer"

## ⚡ Slash Commands

Commands that start with `/` for specific actions.

### /help
Show all available commands and quick tips.

**Usage:**
```
/help
```

**Response:**
Lists all commands with descriptions.

---

### /status
Check your Mac's system status and health.

**Usage:**
```
/status
```

**Shows:**
- 💾 Disk usage (all drives)
- 🧠 Memory usage
- ⏱️ System uptime
- 🖥️ Current load
- 📊 Top processes

**Example Response:**
```
📊 System Status

💾 Disk Usage:
   /System: 45% (150GB free)
   /Users: 72% (80GB free)

🧠 Memory:
   Used: 12GB / 16GB (75%)

⏱️ Uptime: 3 days, 4 hours

🖥️ Load: 2.5 (moderate)
```

---

### /remember
Save a fact or information to bot's memory.

**Usage:**
```
/remember [fact to remember]

Examples:
/remember My favorite color is blue
/remember My wife's birthday is March 15
/remember I prefer tea over coffee
/remember Work VPN password is xyz789
```

**Response:**
```
✅ Got it! I'll remember that.

Saved: "My favorite color is blue"
```

**Notes:**
- Stores in local SQLite database
- Persistent across sessions
- Private to your user
- Categorized automatically

---

### /recall
Display all facts the bot remembers about you.

**Usage:**
```
/recall
```

**Response:**
```
🧠 Here's what I remember about you:

• Your favorite color is blue
• You work at Google
• You prefer tea over coffee
• Your wife's birthday is March 15

💡 Tip: Use /remember to add more!
```

---

### /clear
Clear the conversation history. Bot forgets previous messages.

**Usage:**
```
/clear
```

**Response:**
```
🧹 Conversation history cleared!

I'm starting fresh. What would you like to talk about?
```

**Notes:**
- Only clears conversation, NOT memory (/remember facts)
- Useful for starting a new topic
- Saves database space

---

### /read
Read contents of a text file.

**Usage:**
```
/read [filepath]

Examples:
/read ~/Documents/todo.txt
/read ~/Projects/myapp/README.md
/read /Users/owner/Downloads/notes.txt
```

**Response:**
Displays file contents (truncated if very long).

**Security:**
- Only allowed directories (set in .env)
- Cannot read binary files
- Cannot read files outside allowed paths
- Logs all file access

---

### /list
List contents of a directory.

**Usage:**
```
/list [directory]

Examples:
/list ~/Documents
/list ~/Projects
/list .
```

**Response:**
```
📁 /Users/owner/Projects

drwxr-xr-x  myapp/
drwxr-xr-x  website/
-rw-r--r--  README.md
-rw-r--r--  todo.txt

5 items total
```

**Security:**
- Same restrictions as /read
- Shows file sizes and permissions
- Respects .gitignore (if in git repo)

---

### /exec
Execute a safe shell command.

**Usage:**
```
/exec [command]

Examples:
/exec git status
/exec df -h
/exec date
/exec whoami
```

**Response:**
Shows command output.

**Allowed Commands:**
- `df` - Disk free space
- `du` - Disk usage
- `git` - Git operations
- `ls` - List files
- `cat` - Read files
- `ps` - Process status
- `top` - System processes
- `whoami` - Current user
- `pwd` - Current directory
- `date` - Current date/time
- `cal` - Calendar
- `echo` - Print text
- `head` - First lines of file
- `tail` - Last lines of file
- `wc` - Word count
- `find` - Find files
- `grep` - Search text

**Security:**
- Whitelist only (configured in .env)
- Dangerous commands blocked
- All commands logged
- Cannot modify system files

---

## 🎯 Tips for Best Experience

### 1. Use Natural Language
Don't overthink it! Just chat:
- ✅ "What's the weather?"
- ❌ `/weather` (doesn't exist)

### 2. Be Specific
Better results with details:
- ✅ "Show me Python files in ~/Projects"
- ❌ "Show me files"

### 3. Build Context
The bot remembers conversation:
- You: "I'm working on a React project"
- Later: "How do I add routing?" → Knows you mean React Router

### 4. Use Memory for Important Info
Things to /remember:
- Passwords (encrypted locally)
- Preferences
- Important dates
- Project details
- Contact info

### 5. Check Status Regularly
Use `/status` to monitor:
- Disk space (avoid full drive)
- Memory usage
- System health

## 🚫 Things Bot CANNOT Do

For security, these are blocked:

❌ **Delete files** - Cannot rm, delete, or modify files  
❌ **Install software** - Cannot brew install, apt, etc.  
❌ **Modify system** - Cannot change settings  
❌ **Access all files** - Only allowed directories  
❌ **Run any command** - Only whitelisted safe commands  
❌ **Access other users** - Only responds to @owner  
❌ **Internet access** - Cannot browse web (unless configured)  

## 🆘 Getting Help

If something doesn't work:

1. **Check spelling** - Commands are case-sensitive
2. **Check permissions** - File paths must be allowed
3. **Check logs** - `docker-compose logs -f`
4. **Try /help** - See all available commands
5. **Ask naturally** - "How do I..." works better than guessing commands

## 💡 Pro Tips

### Keyboard Shortcuts (Telegram)
- Type `/` to see command suggestions
- Up arrow for command history
- Tab for autocomplete (in some clients)

### Quick Commands
Set up quick access:
- Pin /status to top of chat
- Create custom keyboard in BotFather
- Use voice messages (if enabled)

### Automation
Set up recurring tasks:
- Daily /status at 9am
- Weekly backup reminder
- Periodic memory cleanup

---

**Remember:** When in doubt, just ask naturally! 🤖
