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

## 📧 Email Commands

Interact with your Gmail inbox directly from Telegram.

> **Setup required:** Run `/email auth` first and complete Gmail OAuth.
> See [EMAIL_SETUP.md](EMAIL_SETUP.md) for step-by-step instructions.

---

### /email auth

Connect your Gmail account via OAuth.

**Usage:**

```
/email auth
```

**Response:** Bot replies with an authorization link. Open it in your browser, sign in with Google, and grant permissions. You'll see a success message in Telegram when done.

---

### /email check

Fetch your latest unread emails (up to 10).

**Usage:**

```
/email check
```

**Example Response:**

```
📧 Unread Emails (3)

1. From: Alice <alice@example.com>
   Subject: Weekend plans?
   Preview: Hey, are you free Saturday...

2. From: GitHub <noreply@github.com>
   Subject: [ronkbot] New issue opened
   Preview: Issue #12: Add voice message support...
```

---

### /email read

Read the full body of a specific email.

**Usage:**

```
/email read [email-id]

Example:
/email read 18c7a3b9f2e1d054
```

**Notes:**

- Get the email ID from `/email check`
- Long emails are truncated to the first 2000 characters
- Cached locally after first read (instant on repeat)

---

### /email reply

Generate 3 AI-powered reply options for an email.

**Usage:**

```
/email reply [email-id]

Example:
/email reply 18c7a3b9f2e1d054
```

**Example Response:**

```
📧 AI-Generated Reply Options

Replying to: Weekend plans?

1️⃣ FORMAL
Thank you for reaching out. I'd be happy to...

2️⃣ CASUAL
Hey! Yeah Saturday works great for me...

3️⃣ BRIEF
Saturday works! What time?
```

**Notes:**

- Uses your writing style profile (run `/email analyze` to build it)
- Reply with `1`, `2`, or `3` to send that option

---

### /email send

Compose and send a new email.

**Usage:**

```
/email send
```

The bot will prompt you for recipient, subject, and body step by step.

---

### /email search

Search your Gmail inbox.

**Usage:**

```
/email search [query]

Examples:
/email search invoice
/email search from:boss@company.com
/email search subject:meeting this week
```

**Notes:**

- Supports Gmail search operators (`from:`, `subject:`, `is:unread`, etc.)
- Returns up to 10 matching emails

---

### /email analyze

Analyze your writing style from sent emails. Used to personalize AI replies.

**Usage:**

```
/email analyze
```

**What it does:**

- Fetches your last 50 sent emails
- Sends them to Gemini for analysis (locally — not stored externally)
- Saves your style profile (formality, tone, greetings, sign-offs)
- Future `/email reply` responses mimic your voice

**Example Response:**

```
✅ Writing Style Analysis Complete!

📊 Your Style Profile:
🎯 Formality: 65% formal
🎭 Tone: professional
👋 Greetings: Hi, Hey, Hello
✍️ Sign-offs: Thanks, Best, Cheers
```

---

## ✅ /todo — Task Management

Manage your todo list directly from Telegram.

---

### /todo

List all active (incomplete) todos. Same as `/todo list`.

**Usage:**

```
/todo
/todo list
```

**Example Response:**

```
✅ Your Todos (3)

1. [#12] Buy groceries
   📅 Due: 2026-03-15 | 🔁 weekly

2. [#13] Call dentist
   📅 Due: 2026-03-14

3. [#14] Daily standup
   🔁 daily
```

---

### /todo add

Create a new todo. Optionally set a due date and recurrence.

**Usage:**

```
/todo add <task> [due:YYYY-MM-DD] [recur:daily|weekly|monthly]

Examples:
/todo add Buy groceries due:2026-03-15 recur:weekly
/todo add Call dentist due:2026-03-14
/todo add Morning meditation recur:daily
/todo add Fix the sink
```

**Response:**

```
✅ Todo created!

#12 — Buy groceries
📅 Due: 2026-03-15
🔁 Recurs: weekly
```

---

### /todo done

Mark a todo as completed by its ID number.

**Usage:**

```
/todo done <id>

Example:
/todo done 12
```

**Response:**

```
✅ Completed: Buy groceries

🔁 Next instance created:
#15 — Buy groceries
📅 Due: 2026-03-22
```

If the todo is recurring, the next instance is automatically created.

---

### /todo delete

Permanently remove a todo by its ID number.

**Usage:**

```
/todo delete <id>

Example:
/todo delete 12
```

**Response:**

```
🗑️ Todo #12 deleted.
```

---

## 🔧 /system — Remote Control (Owner Only)

Control the ronkbot container directly from Telegram. All subcommands are restricted to the owner only (`TELEGRAM_OWNER_USERNAME`).

### /system status

Check whether the ronkbot Docker container is running.

```
/system status
```

**Response:**

```
✅ ronkbot Container Status

NAMES           STATUS          PORTS
ronkbot-n8n     Up 3 hours      0.0.0.0:5678->5678/tcp
```

### /system restart

Gracefully restart the ronkbot container. The bot will go offline for ~30 seconds.

```
/system restart
```

**Response:**

```
🔄 Restarting ronkbot...

I'll be back in ~30 seconds! Use /system status to check.
```

### /system stop

Stop the ronkbot container. To bring it back, use the **Start ronkbot** iOS Shortcut or run `docker start ronkbot-n8n` on the Mac.

```
/system stop
```

**Response:**

```
🛑 ronkbot stopped.

To restart from your iPhone, tap the Start ronkbot Shortcut
or run: docker start ronkbot-n8n
```

### /system wake

Check the Mac's power/sleep status — tells you if the Mac will stay awake when the lid is closed.

```
/system wake
```

**Response (examples):**

```
📱 Wake / Power Status

✅ Mac is plugged in and sleep prevention is active. Bot will stay awake!

Battery: Now drawing from 'AC Power'; 100% charged
```

or

```
📱 Wake / Power Status

⚠️ On AC power but no sleep prevention detected.

Install Amphetamine (free) to stay awake with lid closed:
https://apps.apple.com/us/app/amphetamine/id937984704

Battery: Now drawing from 'AC Power'; 87% charged
```

### Security

- All `/system` commands check that the caller's Telegram username matches `TELEGRAM_OWNER_USERNAME` in your `.env` file.
- Non-owners see: `⛔ Access denied. System commands are owner-only.`

### iPhone Remote Start Setup

To start ronkbot from your iPhone when it's stopped, run once on the Mac:

```bash
bash scripts/create-shortcut.sh
```

This creates a **Start ronkbot** Shortcut that syncs to your iPhone via iCloud. Add it to your Home Screen for one-tap access.

> **Keep your Mac awake:** Install [Amphetamine](https://apps.apple.com/us/app/amphetamine/id937984704) (free, Mac App Store) to stay awake with the lid closed.

---

**Remember:** When in doubt, just ask naturally! 🤖
