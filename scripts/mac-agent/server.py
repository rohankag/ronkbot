#!/usr/bin/env python3
"""
mac-agent/server.py — Local Mac agent server for ronkbot
Receives tool calls from n8n, executes on the Mac, returns results.
Binds to 127.0.0.1 ONLY — never exposed to the internet.
"""
import os, json, time, logging, re, subprocess, webbrowser
sys_path = __import__('sys')
sys_path.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
import brain as Brain
import watchdog as Watchdog
from urllib.parse import unquote_plus
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

# ── Config ───────────────────────────────────────────────────────────────────
PORT = int(os.environ.get("MAC_AGENT_PORT", "4242"))
LOG_DIR = Path.home() / ".ronkbot"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "agent.log"
ALLOWLIST_PATH = Path(__file__).parent / "allowlist.txt"
MAX_OUTPUT = 4000  # max chars of command output to return

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("mac-agent")

# ── Allowlist ────────────────────────────────────────────────────────────────
BLOCKED_PATTERNS = [
    r"\brm\s+-rf\b",
    r"\bsudo\b",
    r"\bmkfs\b",
    r"\bdd\s+if=",
    r"\b>\s*/dev/",
    r":(){ :|:& };:",  # fork bomb
    r"\bcurl\b.*\|\s*bash",
    r"\bwget\b.*\|\s*bash",
    r"\bchmod\s+777\b",
    r"\bshutdown\b",
    r"\breboot\b",
]

# Shell command separators that enable injection
SHELL_SEPARATORS = re.compile(r"[;|&`$]|\|\||&&")

# Allowed directories for file operations (path traversal guard)
ALLOWED_FILE_DIRS = [
    Path.home(),  # ~/ is always allowed
]
# Add user-configured extra dirs from env
for _d in os.environ.get("ALLOWED_DIRECTORIES", "").split(","):
    _d = _d.strip()
    if _d:
        ALLOWED_FILE_DIRS.append(Path(_d).resolve())

# Dangerous AppleScript patterns
BLOCKED_OSASCRIPT = [
    r"\bdo shell script\b",
    r"\bSystem Events\b",
    r"\bkeystroke\b",
    r"\bkey code\b",
]

def load_allowlist() -> list[re.Pattern]:
    """Load allowed command patterns from allowlist.txt."""
    patterns = []
    if ALLOWLIST_PATH.exists():
        for line in ALLOWLIST_PATH.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                try:
                    patterns.append(re.compile(line))
                except re.error:
                    log.warning("Invalid allowlist pattern: %s", line)
    return patterns

ALLOW_PATTERNS = load_allowlist()

def is_allowed(cmd: str) -> tuple[bool, str]:
    """Check if a command is allowed to execute."""
    # Always block dangerous patterns
    for pat in BLOCKED_PATTERNS:
        if re.search(pat, cmd, re.IGNORECASE):
            return False, f"Blocked: matches dangerous pattern '{pat}'"
    # Check allowlist (if empty, allow everything except blocked)
    if ALLOW_PATTERNS:
        for pat in ALLOW_PATTERNS:
            if pat.search(cmd):
                return True, "Allowed by pattern"
        return False, "Not in allowlist"
    return True, "No allowlist configured (permissive mode)"

# ── FastAPI ──────────────────────────────────────────────────────────────────
app = FastAPI(title="ronkbot mac-agent", version="1.0.0")

class ToolRequest(BaseModel):
    tool: str  # shell, osascript, file_read, file_write, notify, open_url
    args: dict  # tool-specific arguments
    confirm: Optional[bool] = False  # requires confirmation?

class ToolResponse(BaseModel):
    success: bool
    tool: str
    output: str
    error: Optional[str] = None

# ── Tool: Shell ──────────────────────────────────────────────────────────────
def tool_shell(args: dict) -> ToolResponse:
    cmd = args.get("command", "")
    if not cmd:
        return ToolResponse(success=False, tool="shell", output="", error="No command provided")
    
    # Block shell injection via command separators (;, &&, ||, |, backticks, $())
    if SHELL_SEPARATORS.search(cmd):
        log.warning("BLOCKED shell (separator): %s", cmd)
        return ToolResponse(success=False, tool="shell", output="",
                            error="Command blocked: shell separators (;|&`$) are not allowed. Use one command at a time.")
    
    allowed, reason = is_allowed(cmd)
    if not allowed:
        log.warning("BLOCKED shell: %s (%s)", cmd, reason)
        return ToolResponse(success=False, tool="shell", output="", error=f"Command blocked: {reason}")
    
    log.info("EXEC shell: %s", cmd)
    try:
        # Use shlex.split + shell=False to prevent injection
        import shlex
        cmd_parts = shlex.split(cmd)
        result = subprocess.run(
            cmd_parts, shell=False, capture_output=True, text=True,
            timeout=30, cwd=args.get("cwd", str(Path.home())),
            env={**os.environ, "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin")},
        )
        output = result.stdout[:MAX_OUTPUT]
        if result.stderr:
            output += "\n[stderr] " + result.stderr[:500]
        return ToolResponse(
            success=result.returncode == 0,
            tool="shell",
            output=output.strip() or "(no output)",
            error=None if result.returncode == 0 else f"Exit code: {result.returncode}",
        )
    except subprocess.TimeoutExpired:
        return ToolResponse(success=False, tool="shell", output="", error="Command timed out (30s)")
    except Exception as e:
        return ToolResponse(success=False, tool="shell", output="", error=str(e))

# ── Tool: AppleScript ────────────────────────────────────────────────────────
def tool_osascript(args: dict) -> ToolResponse:
    script = args.get("script", "")
    if not script:
        return ToolResponse(success=False, tool="osascript", output="", error="No script provided")
    
    # Block dangerous AppleScript patterns (shell escape, keystroke injection)
    for pat in BLOCKED_OSASCRIPT:
        if re.search(pat, script, re.IGNORECASE):
            log.warning("BLOCKED osascript (dangerous pattern): %s", script[:100])
            return ToolResponse(success=False, tool="osascript", output="",
                                error=f"AppleScript blocked: contains dangerous pattern '{pat}'")
    
    log.info("EXEC osascript: %s", script[:100])
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=15,
        )
        return ToolResponse(
            success=result.returncode == 0,
            tool="osascript",
            output=(result.stdout or result.stderr or "(no output)").strip()[:MAX_OUTPUT],
            error=None if result.returncode == 0 else result.stderr[:200],
        )
    except subprocess.TimeoutExpired:
        return ToolResponse(success=False, tool="osascript", output="", error="AppleScript timed out")
    except Exception as e:
        return ToolResponse(success=False, tool="osascript", output="", error=str(e))

# ── Path traversal guard ─────────────────────────────────────────────────────
def _check_path_allowed(p: Path, tool_name: str) -> ToolResponse | None:
    """Return an error ToolResponse if path is outside allowed dirs, else None."""
    resolved = p.resolve()
    for allowed_dir in ALLOWED_FILE_DIRS:
        try:
            resolved.relative_to(allowed_dir)
            return None  # path is within this allowed dir
        except ValueError:
            continue
    log.warning("BLOCKED %s (path traversal): %s", tool_name, resolved)
    return ToolResponse(success=False, tool=tool_name, output="",
                        error=f"Path blocked: {resolved} is outside allowed directories")

# ── Tool: File Read ──────────────────────────────────────────────────────────
def tool_file_read(args: dict) -> ToolResponse:
    path = args.get("path", "")
    if not path:
        return ToolResponse(success=False, tool="file_read", output="", error="No path provided")
    
    p = Path(path).expanduser()
    # Path traversal guard
    blocked = _check_path_allowed(p, "file_read")
    if blocked:
        return blocked
    if not p.exists():
        return ToolResponse(success=False, tool="file_read", output="", error=f"File not found: {p}")
    
    log.info("READ file: %s", p)
    try:
        content = p.read_text(errors="replace")[:MAX_OUTPUT]
        return ToolResponse(success=True, tool="file_read", output=content)
    except Exception as e:
        return ToolResponse(success=False, tool="file_read", output="", error=str(e))

# ── Tool: File Write ─────────────────────────────────────────────────────────
def tool_file_write(args: dict) -> ToolResponse:
    path = args.get("path", "")
    content = args.get("content", "")
    append = args.get("append", False)
    if not path:
        return ToolResponse(success=False, tool="file_write", output="", error="No path provided")
    
    p = Path(path).expanduser()
    # Path traversal guard
    blocked = _check_path_allowed(p, "file_write")
    if blocked:
        return blocked
    log.info("WRITE file: %s (append=%s)", p, append)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        if append:
            with open(p, "a") as f:
                f.write(content)
        else:
            p.write_text(content)
        return ToolResponse(success=True, tool="file_write", output=f"Written to {p} ({len(content)} chars)")
    except Exception as e:
        return ToolResponse(success=False, tool="file_write", output="", error=str(e))

# ── Tool: macOS Notification ─────────────────────────────────────────────────
def tool_notify(args: dict) -> ToolResponse:
    title = args.get("title", "ronkbot")
    message = args.get("message", "")
    if not message:
        return ToolResponse(success=False, tool="notify", output="", error="No message provided")
    
    script = f'display notification "{message}" with title "{title}"'
    return tool_osascript({"script": script})

# ── Tool: Open URL ───────────────────────────────────────────────────────────
def tool_open_url(args: dict) -> ToolResponse:
    url = args.get("url", "")
    if not url:
        return ToolResponse(success=False, tool="open_url", output="", error="No URL provided")
    
    # Only allow http/https — block file://, javascript:, data:, etc.
    from urllib.parse import urlparse
    scheme = urlparse(url).scheme.lower()
    if scheme not in ("http", "https"):
        log.warning("BLOCKED open_url (invalid scheme %r): %s", scheme, url)
        return ToolResponse(success=False, tool="open_url", output="",
                            error=f"URL blocked: only http/https schemes are allowed (got '{scheme}')")
    
    log.info("OPEN url: %s", url)
    try:
        webbrowser.open(url)
        return ToolResponse(success=True, tool="open_url", output=f"Opened: {url}")
    except Exception as e:
        return ToolResponse(success=False, tool="open_url", output="", error=str(e))

# ── Tool Router ──────────────────────────────────────────────────────────────
# ── Tool: Brain Note (AI self-stores facts) ────────────────────────────────
def tool_brain_note(args: dict) -> ToolResponse:
    chat_id = args.get("chat_id", "default")
    fact    = args.get("fact", "")
    category = args.get("category", "fact")
    source   = args.get("source", "extracted")
    if not fact:
        return ToolResponse(success=False, tool="brain_note", output="", error="No fact provided")
    log.info("BRAIN NOTE [%s]: %s", category, fact[:100])
    result = Brain.store_fact(chat_id, fact, category=category, source=source)
    return ToolResponse(success=True, tool="brain_note",
                        output=f"{result['status']}: {fact[:80]}")

def tool_brain_recall(args: dict) -> ToolResponse:
    chat_id = args.get("chat_id", "default")
    query   = args.get("query", "")
    facts = Brain.search_facts(chat_id, query=query, limit=8)
    if not facts:
        return ToolResponse(success=True, tool="brain_recall", output="No matching memories found.")
    lines = [f"• [{f['category']}] {f['fact']}" for f in facts]
    return ToolResponse(success=True, tool="brain_recall", output="\n".join(lines))

def tool_brain_stats(args: dict) -> ToolResponse:
    chat_id = args.get("chat_id", "default")
    stats = Brain.get_stats(chat_id)
    lines = [
        f"🧠 **Brain Stats**",
        f"  Facts stored: {stats['knowledge_facts']}",
        f"  Messages remembered: {stats['working_messages']}",
        f"  Episodic log: {stats['episode_count']} entries",
        f"  Reflections: {stats['reflections']}",
        f"  Oldest memory: {(stats['oldest_memory'] or 'n/a')[:10]}",
        f"  DB size: {stats['db_size_kb']} KB",
    ]
    return ToolResponse(success=True, tool="brain_stats", output="\n".join(lines))

def tool_brain_new_session(args: dict) -> ToolResponse:
    chat_id = args.get("chat_id", "default")
    window_id = Brain.clear_conversation_window(chat_id)
    return ToolResponse(success=True, tool="brain_new_session",
                        output=f"New session started (window {window_id}). History preserved.")

TOOLS = {
    "shell": tool_shell,
    "osascript": tool_osascript,
    "file_read": tool_file_read,
    "file_write": tool_file_write,
    "notify": tool_notify,
    "open_url": tool_open_url,
    "brain_note": tool_brain_note,
    "brain_recall": tool_brain_recall,
    "brain_stats": tool_brain_stats,
    "brain_new_session": tool_brain_new_session,
}

@app.post("/execute", response_model=ToolResponse)
async def execute(req: ToolRequest):
    """Execute a tool call from n8n."""
    if req.tool not in TOOLS:
        raise HTTPException(400, f"Unknown tool: {req.tool}. Available: {list(TOOLS.keys())}")
    
    log.info("── Tool call: %s | args: %s", req.tool, json.dumps(req.args)[:200])
    result = TOOLS[req.tool](req.args)
    log.info("── Result: success=%s output=%s", result.success, result.output[:100])
    return result

@app.get("/health")
async def health():
    return {"status": "ok", "tools": list(TOOLS.keys()), "pid": os.getpid()}

@app.get("/health/full")
async def health_full():
    """Extended health check including watchdog status."""
    wd = Watchdog.get_state()
    return {
        "status": "ok",
        "tools": list(TOOLS.keys()),
        "pid": os.getpid(),
        "watchdog": wd,
    }

# ── Thinking Protocol ────────────────────────────────────────────────────────

class ParseThinkingRequest(BaseModel):
    text: str  # Full AI response potentially containing <think>...</think>

@app.post("/brain/parse-thinking")
async def parse_thinking(req: ParseThinkingRequest):
    """Parse <think>...</think> blocks from AI response.
    Returns the thinking text and the cleaned response separately.
    Called by n8n Code node after the AI Agent.
    """
    import re as _re
    text = req.text or ""

    # Extract all <think>...</think> blocks
    think_pattern = _re.compile(r'<think>(.*?)</think>', _re.DOTALL)
    think_matches = think_pattern.findall(text)

    thinking = " ".join(m.strip() for m in think_matches).strip() if think_matches else ""

    # Remove <think> blocks from the response
    clean_response = think_pattern.sub("", text).strip()

    return {
        "thinking": thinking,
        "response": clean_response,
        "had_thinking": bool(thinking),
    }

@app.get("/brain/parse-thinking")
async def parse_thinking_get(text: str = ""):
    """GET version of parse-thinking for n8n compatibility."""
    import re as _re
    text = unquote_plus(text)

    think_pattern = _re.compile(r'<think>(.*?)</think>', _re.DOTALL)
    think_matches = think_pattern.findall(text)

    thinking = " ".join(m.strip() for m in think_matches).strip() if think_matches else ""
    clean_response = think_pattern.sub("", text).strip()

    return {
        "thinking": thinking,
        "response": clean_response,
        "had_thinking": bool(thinking),
    }

@app.get("/tools")
async def list_tools():
    """List available tools and their descriptions."""
    return {
        "tools": [
            {"name": "shell", "description": "Run a shell command", "args": ["command", "cwd?"]},
            {"name": "osascript", "description": "Run AppleScript (open apps, control media, etc.)", "args": ["script"]},
            {"name": "file_read", "description": "Read a file's contents", "args": ["path"]},
            {"name": "file_write", "description": "Write/append to a file", "args": ["path", "content", "append?"]},
            {"name": "notify", "description": "Send a macOS notification", "args": ["title?", "message"]},
            {"name": "open_url", "description": "Open a URL in the default browser", "args": ["url"]},
        ]
    }

# ── Brain REST API ──────────────────────────────────────────────────────────
class SaveMessageRequest(BaseModel):
    chat_id: str
    role: str
    content: str
    provider: Optional[str] = None
    tool_call: Optional[dict] = None
    window_id: Optional[str] = None

class RememberRequest(BaseModel):
    chat_id: str
    fact: str
    category: Optional[str] = "fact"
    key_topic: Optional[str] = "general"
    source: Optional[str] = "explicit"

class CompactRequest(BaseModel):
    chat_id: str
    summary: str
    message_count: int
    facts: Optional[list] = []

class MoodRequest(BaseModel):
    chat_id: str
    mood: str
    confidence: Optional[float] = 0.5
    trigger: Optional[str] = None

@app.get("/brain/context")
async def brain_context(chat_id: str, message: str = "", save: str = "0"):
    """Assemble full AI context: soul + facts + messages + MEMORY.md.
    Read-only endpoint — saving is handled by the Save User Msg node.
    """
    try:
        ctx = Brain.assemble_context(chat_id, message)
        return {"ok": True, **ctx}
    except Exception as e:
        log.error("brain/context error: %s", e)
        raise HTTPException(500, str(e))

@app.get("/brain/save-get")
async def brain_save_get(chat_id: str, role: str, content: str, provider: Optional[str] = None):
    """GET-based brain save endpoint (for n8n compatibility where POST body encoding fails).
    Handles URL-encoded content and enforces length limits."""
    try:
        # URL-decode content (n8n sends it as query param which gets encoded)
        decoded = unquote_plus(content or "")
        if not decoded.strip():
            return {"ok": True, "message_count": 0, "skipped": "empty content"}
        saved = Brain.save_message(chat_id, role, decoded, provider=provider)
        count = Brain.count_recent_messages(chat_id)
        if saved:
            log.info("brain/save-get: saved [%s] %s for %s", role, decoded[:40], chat_id)
        else:
            log.info("brain/save-get: deduped [%s] for %s", role, chat_id)
        return {"ok": True, "message_count": count, "was_duplicate": not saved}
    except Exception as e:
        log.error("brain/save-get error: %s", e)
        raise HTTPException(500, str(e))

@app.get("/brain/extract")
async def brain_extract(chat_id: str, user_text: str = "", ai_text: str = ""):
    """Auto-extract durable facts from a conversation turn using Groq.
    Called by n8n after each AI response. Best-effort: never blocks the main flow."""
    import httpx
    try:
        user_text = unquote_plus(user_text or "")
        ai_text = unquote_plus(ai_text or "")
        
        if len(user_text) < 5 or len(ai_text) < 20:
            return {"ok": True, "extracted": 0, "skipped": "messages too short"}
        
        # Groq API key — same one used by n8n
        groq_key = os.environ.get("GROQ_API_KEY", "")
        if not groq_key:
            return {"ok": True, "extracted": 0, "skipped": "GROQ_API_KEY not configured"}
        
        prompt = (
            "Extract durable facts about the user from this conversation. "
            "Only extract facts useful to remember long-term (preferences, personal info, habits, context).\n\n"
            f"User said: \"{user_text[:500]}\"\n"
            f"Assistant replied: \"{ai_text[:500]}\"\n\n"
            "Return a JSON array: [{\"fact\": \"...\", \"category\": \"preference|fact|habit|context\", \"key_topic\": \"...\"}]\n"
            "Return [] if nothing worth remembering. Be selective."
        )
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 300,
                    "temperature": 0.1,
                },
            )
            data = resp.json()
        
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "[]")
        
        # Parse JSON array
        facts = []
        import re as _re
        match = _re.search(r'\[.*\]', content, _re.DOTALL)
        if match:
            try:
                facts = json.loads(match.group())
            except json.JSONDecodeError:
                pass
        
        # Store each fact
        stored = 0
        for f in facts:
            fact_text = f.get("fact", "")
            if fact_text and len(fact_text) > 5:
                Brain.store_fact(
                    chat_id, fact_text,
                    category=f.get("category", "fact"),
                    key_topic=f.get("key_topic", "general"),
                    source="extracted",
                    confidence=float(f.get("confidence", 0.8)),
                )
                stored += 1
                log.info("brain/extract: stored fact [%s] %s", f.get("category"), fact_text[:50])
        
        return {"ok": True, "extracted": stored, "total_found": len(facts)}
    except Exception as e:
        log.error("brain/extract error: %s", e)
        return {"ok": True, "extracted": 0, "error": str(e)[:200]}

@app.post("/brain/save")
async def brain_save(req: SaveMessageRequest):
    """Save a message to working memory + episodic log."""
    try:
        Brain.save_message(
            req.chat_id, req.role, req.content,
            provider=req.provider, tool_call=req.tool_call, window_id=req.window_id
        )
        # Check if we should trigger compaction (every 20 messages)
        count = Brain.count_recent_messages(req.chat_id)
        needs_compact = count > 0 and count % 20 == 0
        return {"ok": True, "message_count": count, "needs_compaction": needs_compact}
    except Exception as e:
        log.error("brain/save error: %s", e)
        raise HTTPException(500, str(e))

@app.post("/brain/remember")
async def brain_remember(req: RememberRequest):
    """Explicitly store a fact in the knowledge base."""
    try:
        result = Brain.store_fact(
            req.chat_id, req.fact,
            category=req.category, key_topic=req.key_topic, source=req.source
        )
        return {"ok": True, **result}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/brain/recall")
async def brain_recall(chat_id: str, q: str, limit: int = 8):
    """Search knowledge base."""
    facts = Brain.search_facts(chat_id, query=q, limit=limit)
    return {"ok": True, "facts": facts, "count": len(facts)}

@app.get("/brain/search")
async def brain_search(q: str, chat_id: Optional[str] = None, limit: int = 10):
    """Full-text search over episodic history."""
    results = Brain.search_history(q, chat_id=chat_id, limit=limit)
    return {"ok": True, "results": results, "count": len(results)}

@app.get("/brain/stats")
async def brain_stats(chat_id: str):
    """Return brain statistics for a chat."""
    return {"ok": True, **Brain.get_stats(chat_id)}

@app.post("/brain/compact")
async def brain_compact(req: CompactRequest):
    """Save a compaction summary and extracted facts."""
    try:
        # Store extracted facts
        for f in req.facts:
            Brain.store_fact(
                req.chat_id,
                f.get("fact", ""),
                category=f.get("category", "fact"),
                key_topic=f.get("key_topic", "general"),
                confidence=float(f.get("confidence", 0.8)),
                source="extracted"
            )
        # Save reflection
        Brain.save_reflection(req.chat_id, req.summary, req.message_count, len(req.facts))
        # Update MEMORY.md if facts extracted
        if req.facts:
            facts_md = "\n".join([f"- {f.get('fact','')}" for f in req.facts])
            Brain.update_memory_md(facts_md, section="Recent Learnings")
        return {"ok": True, "facts_stored": len(req.facts)}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/brain/mood")
async def brain_mood(req: MoodRequest):
    """Log a mood observation."""
    Brain.log_mood(req.chat_id, req.mood, req.confidence, req.trigger)
    return {"ok": True}

@app.post("/brain/reflect")
async def brain_reflect(chat_id: str = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "")):
    """Trigger daily reflection: summarize conversations, update MEMORY.md."""
    try:
        result = Brain.run_daily_reflection(chat_id)
        return {"ok": True, **result}
    except Exception as e:
        log.error("brain/reflect error: %s", e)
        raise HTTPException(500, str(e))

@app.post("/brain/checkpoint")
async def brain_checkpoint():
    """Force a WAL checkpoint to compact the database."""
    Brain.wal_checkpoint()
    return {"ok": True, "message": "WAL checkpoint complete"}

@app.delete("/brain/session")
async def brain_new_session(chat_id: str):
    """Start a new conversation window (for /new command)."""
    window_id = Brain.clear_conversation_window(chat_id)
    return {"ok": True, "window_id": window_id, "message": "New session started — history preserved in episodic log"}

@app.get("/brain/export")
async def brain_export(chat_id: str):
    """Export full brain as JSON."""
    soul = Brain.load_soul()
    facts = Brain.search_facts(chat_id, limit=500)
    messages = Brain.get_context_messages(chat_id, limit=200)
    stats = Brain.get_stats(chat_id)
    return {"soul": soul, "facts": facts, "recent_messages": messages, "stats": stats}

# ── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    log.info("🖥️  mac-agent starting on 127.0.0.1:%d", PORT)
    log.info("   Log: %s", LOG_FILE)
    log.info("   Allowlist: %s (%d patterns)", ALLOWLIST_PATH, len(ALLOW_PATTERNS))
    log.info("   Brain DB: %s", Brain.BRAIN_DB)
    # Start self-healing watchdog
    Watchdog.start_watchdog()
    log.info("🐕 Watchdog thread started")
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")


# ── Owner identity (Docker-accessible) ──────────────────────────────────────
@app.get("/brain/owner")
async def brain_owner():
    """Return owner identity from soul.yaml. Used by Docker cron workflows
    that cannot access ~/.ronkbot/ directly."""
    soul = Brain.load_soul()
    identity = soul.get("identity", {})
    return {
        "ok": True,
        "chat_id": str(identity.get("telegram_chat_id", "")),
        "username": identity.get("telegram_username", ""),
        "name": identity.get("owner", ""),
    }


# ── TODOs ────────────────────────────────────────────────────────────────────
class TodoCreateRequest(BaseModel):
    chat_id: str
    task: str
    due_at: Optional[str] = None
    remind_at: Optional[str] = None
    recurrence: Optional[str] = None

class TodoUpdateRequest(BaseModel):
    completed: Optional[bool] = None
    reminder_sent: Optional[bool] = None
    task: Optional[str] = None
    due_at: Optional[str] = None
    remind_at: Optional[str] = None
    recurrence: Optional[str] = None

@app.post("/brain/todo")
async def create_todo(req: TodoCreateRequest):
    """Create a new TODO item."""
    result = Brain.create_todo(
        req.chat_id, req.task, due_at=req.due_at,
        remind_at=req.remind_at, recurrence=req.recurrence
    )
    return {"ok": True, **result}

@app.get("/brain/todos")
async def get_todos(chat_id: str, completed: bool = False,
                    due_today: bool = False, due_soon: Optional[int] = None):
    """List todos. ?due_soon=15 returns items with remind_at in next 15 minutes."""
    todos = Brain.get_todos(chat_id, completed=completed,
                            due_today=due_today, due_soon_minutes=due_soon)
    return {"ok": True, "todos": todos, "count": len(todos)}

@app.patch("/brain/todo/{todo_id}")
async def update_todo(todo_id: int, req: TodoUpdateRequest):
    """Update a todo (mark complete, mark reminder sent, etc)."""
    updates = req.dict(exclude_none=True)
    result = Brain.update_todo(todo_id, **updates)
    if not result.get("ok"):
        raise HTTPException(404, "Todo not found")
    return result

@app.delete("/brain/todo/{todo_id}")
async def delete_todo(todo_id: int):
    """Delete a todo by ID."""
    ok = Brain.delete_todo(todo_id)
    if not ok:
        raise HTTPException(404, "Todo not found")
    return {"ok": True}


# ── Alert suppression ────────────────────────────────────────────────────────
@app.get("/brain/alert-check")
async def alert_check(type: str):
    """Check whether an alert should fire (respects suppression window)."""
    return {"ok": True, "type": type, "should_alert": Brain.should_alert(type)}

@app.post("/brain/alert-ack")
async def alert_ack(type: str):
    """Record that an alert was sent, starting the suppression window."""
    Brain.ack_alert(type)
    return {"ok": True, "type": type}


# ── Nightly + Consolidation ──────────────────────────────────────────────────
@app.post("/brain/nightly")
async def brain_nightly(chat_id: Optional[str] = None):
    """Trigger nightly processing: AI reflection + journal (one Groq LLM call)."""
    target = chat_id or Brain.get_owner_chat_id()
    try:
        result = Brain.run_nightly(target)
        return {"ok": True, **result}
    except Exception as e:
        log.error("brain/nightly error: %s", e)
        raise HTTPException(500, str(e))

@app.post("/brain/consolidate")
async def brain_consolidate(chat_id: Optional[str] = None):
    """Trigger memory consolidation: prune stale facts, merge by topic."""
    target = chat_id or Brain.get_owner_chat_id()
    try:
        result = Brain.run_memory_consolidation(target)
        return {"ok": True, **result}
    except Exception as e:
        log.error("brain/consolidate error: %s", e)
        raise HTTPException(500, str(e))
