#!/usr/bin/env python3
"""
brain.py — ronkbot persistent memory system
Five-layer architecture:
  1. Soul        — YAML identity/personality config
  2. Working     — Rolling conversation context (SQLite)
  3. Semantic    — Long-term knowledge base (SQLite)
  4. Episodic    — Immutable, append-only history (SQLite)
  5. Reflective  — Daily compaction + MEMORY.md summaries
"""
import os, json, yaml, sqlite3, hashlib, re, threading
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional
from urllib.parse import unquote_plus

# ── Paths ──────────────────────────────────────────────────────────────────
BRAIN_DIR      = Path.home() / ".ronkbot" / "brain"
BRAIN_DB       = BRAIN_DIR / "brain.db"
SOUL_FILE      = BRAIN_DIR / "soul.yaml"
MEMORY_MD      = BRAIN_DIR / "memory" / "MEMORY.md"
DAILY_DIR      = BRAIN_DIR / "memory" / "daily"
SESSIONS_DIR   = BRAIN_DIR / "memory" / "sessions"
BACKUPS_DIR    = BRAIN_DIR / "backups"

for d in [BRAIN_DIR, BRAIN_DIR / "memory", DAILY_DIR, SESSIONS_DIR, BACKUPS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── DB init ─────────────────────────────────────────────────────────────────
MAX_CONTENT_LEN = 2000          # Truncate working_memory content to this
WORKING_MEMORY_LIMIT = 200      # Max rows per chat_id in working_memory
DEDUP_WINDOW_SEC = 5            # Ignore identical saves within this window

_thread_local = threading.local()

def get_db() -> sqlite3.Connection:
    """Return a cached per-thread SQLite connection."""
    conn = getattr(_thread_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(str(BRAIN_DB), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _thread_local.conn = conn
    return conn

def init_db():
    with get_db() as conn:
        conn.executescript("""
        -- Layer 2: Working memory (rolling context)
        CREATE TABLE IF NOT EXISTS working_memory (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id     TEXT NOT NULL,
            role        TEXT NOT NULL,      -- user / assistant / system / tool
            content     TEXT NOT NULL,
            timestamp   TEXT NOT NULL,      -- ISO8601 UTC
            provider    TEXT,               -- github / groq / gemini / ollama / mac-agent
            tool_call   TEXT,               -- JSON tool call + result if any
            window_id   TEXT                -- conversation boundary (for /new)
        );
        CREATE INDEX IF NOT EXISTS idx_wm_chat ON working_memory(chat_id, timestamp DESC);

        -- Layer 3: Semantic knowledge base (permanent facts)
        CREATE TABLE IF NOT EXISTS knowledge (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id       TEXT NOT NULL,
            category      TEXT NOT NULL,   -- preference, fact, relationship, skill, context, habit
            key_topic     TEXT NOT NULL,
            fact          TEXT NOT NULL,
            confidence    REAL DEFAULT 0.9,
            source        TEXT NOT NULL,   -- explicit / extracted / inferred
            created_at    TEXT NOT NULL,
            updated_at    TEXT NOT NULL,
            last_accessed TEXT,
            access_count  INTEGER DEFAULT 0,
            fact_hash     TEXT UNIQUE      -- prevents exact duplicates
        );
        CREATE INDEX IF NOT EXISTS idx_k_chat ON knowledge(chat_id);
        CREATE INDEX IF NOT EXISTS idx_k_topic ON knowledge(key_topic);
        CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
            fact, key_topic, category, content=knowledge, content_rowid=id
        );

        -- Layer 4: Episodic log (APPEND-ONLY — no UPDATE/DELETE)
        CREATE TABLE IF NOT EXISTS episodes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id     TEXT NOT NULL,
            direction   TEXT NOT NULL,     -- inbound / outbound / tool
            content     TEXT NOT NULL,
            metadata    TEXT,              -- JSON: provider, tokens, tool info
            timestamp   TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_ep_chat ON episodes(chat_id, timestamp);
        CREATE VIRTUAL TABLE IF NOT EXISTS episodes_fts USING fts5(
            content, content=episodes, content_rowid=id
        );

        -- Layer 5: Reflective memory (compaction summaries)
        CREATE TABLE IF NOT EXISTS reflections (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id       TEXT NOT NULL,
            reflection_date TEXT NOT NULL, -- YYYY-MM-DD
            summary       TEXT NOT NULL,   -- AI-generated summary
            message_count INTEGER,
            facts_extracted INTEGER DEFAULT 0,
            created_at    TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_ref_chat ON reflections(chat_id, reflection_date);

        -- Mood tracking (part of soul runtime state)
        CREATE TABLE IF NOT EXISTS mood_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id     TEXT NOT NULL,
            mood        TEXT NOT NULL,     -- neutral / positive / stressed / excited / frustrated
            confidence  REAL DEFAULT 0.5,
            detected_at TEXT NOT NULL,
            trigger     TEXT               -- what message triggered the mood change
        );

        -- Proactive tasks & reminders
        CREATE TABLE IF NOT EXISTS todos (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id         TEXT NOT NULL,
            task            TEXT NOT NULL,
            due_at          TEXT,           -- ISO8601 UTC
            remind_at       TEXT,           -- ISO8601 UTC (separate from due_at)
            recurrence      TEXT,           -- null | 'daily' | 'weekly' | 'monthly'
            completed       BOOLEAN DEFAULT 0,
            reminder_sent   BOOLEAN DEFAULT 0,
            created_at      TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_todos_chat ON todos(chat_id, completed);

        -- Alert suppression state (for anomaly monitor)
        CREATE TABLE IF NOT EXISTS alerts (
            alert_type      TEXT PRIMARY KEY,  -- 'disk_full', 'high_memory'
            last_alerted    TEXT,              -- ISO8601 UTC
            suppression_hours INTEGER DEFAULT 4
        );

        -- Inner monologue journal (nightly)
        CREATE TABLE IF NOT EXISTS inner_journal (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            date        DATE UNIQUE,
            entry       TEXT,
            patterns    TEXT,              -- JSON array of recurring themes
            improvements TEXT,            -- JSON array of self-identified improvements
            created_at  TEXT NOT NULL
        );
        """)
        conn.commit()
    migrate_db()


def migrate_db():
    """Add new columns to existing tables idempotently.
    Safe to run on every startup — ALTER TABLE ADD COLUMN fails silently if column exists."""
    conn = get_db()
    migrations = [
        # Phase 3: reflection AI fields
        "ALTER TABLE reflections ADD COLUMN lesson TEXT",
        "ALTER TABLE reflections ADD COLUMN category TEXT",
        "ALTER TABLE reflections ADD COLUMN applied BOOLEAN DEFAULT 0",
        # Phase 4: episodic enrichment
        "ALTER TABLE episodes ADD COLUMN tools_used TEXT",
        "ALTER TABLE episodes ADD COLUMN success BOOLEAN",
        "ALTER TABLE episodes ADD COLUMN duration_ms INTEGER",
        "ALTER TABLE episodes ADD COLUMN situation TEXT",
        "ALTER TABLE episodes ADD COLUMN outcome TEXT",
    ]
    for sql in migrations:
        try:
            conn.execute(sql)
        except Exception:
            pass  # Column already exists — safe to ignore
    conn.commit()


init_db()

# ── Soul ───────────────────────────────────────────────────────────────────
def get_owner_chat_id() -> str:
    """Get owner's Telegram chat_id from soul config."""
    soul = load_soul()
    fallback = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "")
    return str(soul.get("identity", {}).get("telegram_chat_id", fallback))


# Default soul — personal values come from env vars at runtime
_owner_name = os.environ.get("OWNER_NAME", "Owner")
_owner_username = os.environ.get("TELEGRAM_OWNER_USERNAME", "owner")
_owner_chat_id = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "")

DEFAULT_SOUL = {
    "identity": {
        "name": "ronku_bot",
        "owner": f"{_owner_name} (@{_owner_username})",
        "telegram_chat_id": _owner_chat_id,
        "telegram_username": _owner_username,
        "created": "2026-02-08",
        "version": 2
    },
    "personality": {
        "tone": "friendly, witty, concise",
        "humor": "dry, occasional puns",
        "verbosity": "low — 2-3 sentence replies unless depth requested",
        "emoji_use": "moderate",
        "formality": "casual"
    },
    "values": [
        "privacy_first: Never share owner's data. Route sensitive content to local AI.",
        "honesty: Admit uncertainty. Say 'I don't know' rather than guess.",
        "helpfulness: Bias toward action. Do the thing, then report.",
        "safety: Never execute destructive commands without confirmation."
    ],
    "boundaries": [
        "Do not pretend to be human when sincerely asked",
        "Do not store or process passwords outside local Ollama",
        "Respect rate limits on external APIs"
    ],
    "context": {
        "owner_timezone": "America/New_York",
        "owner_location": "New York",
        "primary_machine": "MacBook Pro M4 Max",
        "coding_projects": "~/coding/LC/projects/",
        "preferred_language": "Python, TypeScript"
    },
    "quirks": {
        "greeting": "Uses owner's first name casually",
        "error_style": "Self-deprecating ('Oops, I tripped over that one')",
        "celebration": "Uses 🎉 for successful tool calls",
        "thinking": "Transparent about uncertainty ('not sure about this one but...')"
    }
}

def load_soul() -> dict:
    """Load soul config. Creates default if missing."""
    if not SOUL_FILE.exists():
        with open(SOUL_FILE, "w") as f:
            yaml.dump(DEFAULT_SOUL, f, default_flow_style=False, sort_keys=False)
    with open(SOUL_FILE) as f:
        return yaml.safe_load(f)

def soul_to_system_prompt(soul: dict) -> str:
    """Convert soul config into a system prompt segment."""
    s = soul
    ident = s.get("identity", {})
    pers = s.get("personality", {})
    ctx = s.get("context", {})
    vals = s.get("values", [])
    bounds = s.get("boundaries", [])
    quirks = s.get("quirks", {})

    lines = [
        f"You are {ident.get('name', 'ronku_bot')}, a personal AI assistant.",
        f"Owner: {ident.get('owner', 'unknown')}.",
        "",
        f"Personality: {pers.get('tone', '')}. Humor: {pers.get('humor', '')}.",
        f"Reply length: {pers.get('verbosity', 'concise')}.",
        f"Emoji: {pers.get('emoji_use', 'moderate')}. Formality: {pers.get('formality', 'casual')}.",
        "",
        "Core values:",
    ]
    for v in vals:
        lines.append(f"- {v}")
    lines.append("")
    lines.append("Hard boundaries:")
    for b in bounds:
        lines.append(f"- {b}")
    lines.append("")
    lines.append(f"Owner context: timezone={ctx.get('owner_timezone','EST')}, "
                 f"location={ctx.get('owner_location','')}, "
                 f"machine={ctx.get('primary_machine','Mac')}, "
                 f"prefers {ctx.get('preferred_language','Python')}.")
    lines.append("")
    lines.append(f"Style quirks: {json.dumps(quirks)}")
    return "\n".join(lines)

# ── Layer 2: Working Memory ─────────────────────────────────────────────────
def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()

def _is_duplicate(conn, chat_id: str, role: str, content: str) -> bool:
    """Check if this exact message was saved within the dedup window."""
    row = conn.execute(
        "SELECT timestamp FROM working_memory "
        "WHERE chat_id = ? AND role = ? AND content = ? "
        "ORDER BY timestamp DESC LIMIT 1",
        (chat_id, role, content)
    ).fetchone()
    if not row:
        return False
    try:
        last_ts = datetime.fromisoformat(row["timestamp"])
        return (datetime.now(timezone.utc) - last_ts).total_seconds() < DEDUP_WINDOW_SEC
    except (ValueError, TypeError):
        return False

def _rotate_working_memory(conn, chat_id: str):
    """Keep only the last WORKING_MEMORY_LIMIT rows per chat_id.
    Older messages are preserved in the episodes table."""
    count = conn.execute(
        "SELECT COUNT(*) as n FROM working_memory WHERE chat_id = ?",
        (chat_id,)
    ).fetchone()["n"]
    if count > WORKING_MEMORY_LIMIT:
        excess = count - WORKING_MEMORY_LIMIT
        conn.execute(
            "DELETE FROM working_memory WHERE id IN ("
            "  SELECT id FROM working_memory WHERE chat_id = ? "
            "  ORDER BY timestamp ASC LIMIT ?"
            ")",
            (chat_id, excess)
        )

def save_message(chat_id: str, role: str, content: str,
                 provider: str = None, tool_call: dict = None,
                 window_id: str = None) -> bool:
    """Save a message to working memory + episodic log.
    Returns False if skipped as duplicate."""
    # Truncate content for working memory (episodic keeps full)
    wm_content = content[:MAX_CONTENT_LEN] if content else ""
    ts = now_utc()
    conn = get_db()
    try:
        # Dedup guard: skip if identical message saved within last N seconds
        if _is_duplicate(conn, chat_id, role, wm_content):
            return False

        conn.execute(
            "INSERT INTO working_memory (chat_id, role, content, timestamp, provider, tool_call, window_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (chat_id, role, wm_content, ts, provider,
             json.dumps(tool_call) if tool_call else None, window_id)
        )
        # Also write to immutable episodic log (full content, no truncation)
        direction = "inbound" if role == "user" else ("outbound" if role == "assistant" else "tool")
        conn.execute(
            "INSERT INTO episodes (chat_id, direction, content, metadata, timestamp) VALUES (?, ?, ?, ?, ?)",
            (chat_id, direction, content,
             json.dumps({"provider": provider, "role": role}), ts)
        )
        # Rotate working memory to keep bounded
        _rotate_working_memory(conn, chat_id)
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    # Append to today's daily markdown log
    _append_daily_log(chat_id, role, wm_content, ts)
    return True

def get_context_messages(chat_id: str, limit: int = 50) -> list[dict]:
    """Get recent messages for AI context injection."""
    conn = get_db()
    rows = conn.execute(
        "SELECT role, content, timestamp, provider FROM working_memory "
        "WHERE chat_id = ? ORDER BY timestamp DESC LIMIT ?",
        (chat_id, limit)
    ).fetchall()
    # Reverse so oldest first (correct AI message order)
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

def count_recent_messages(chat_id: str, since_last_compaction: bool = True) -> int:
    """Count messages since last compaction (used for compaction trigger)."""
    with get_db() as conn:
        # Find last compaction
        last = conn.execute(
            "SELECT MAX(created_at) as ts FROM reflections WHERE chat_id = ?",
            (chat_id,)
        ).fetchone()
        last_ts = last["ts"] or "2000-01-01"
        count = conn.execute(
            "SELECT COUNT(*) as n FROM working_memory WHERE chat_id = ? AND timestamp > ?",
            (chat_id, last_ts)
        ).fetchone()
    return count["n"]

def clear_conversation_window(chat_id: str) -> str:
    """Start a new conversation window (for /new). Does NOT delete episodic log."""
    window_id = hashlib.md5(now_utc().encode()).hexdigest()[:8]
    # We don't delete — we just set a new window_id on future messages
    # The context loader respects the current window
    return window_id

# ── Layer 3: Semantic Memory ────────────────────────────────────────────────
def store_fact(chat_id: str, fact: str, category: str = "fact",
               key_topic: str = "general", source: str = "explicit",
               confidence: float = 0.9) -> dict:
    """Store a fact in the knowledge base. Deduplicates by content hash."""
    fact_hash = hashlib.md5(f"{chat_id}:{fact.strip().lower()}".encode()).hexdigest()
    ts = now_utc()
    conn = get_db()

    existing = conn.execute(
        "SELECT id, access_count FROM knowledge WHERE fact_hash = ?",
        (fact_hash,)
    ).fetchone()

    if existing:
        conn.execute(
            "UPDATE knowledge SET updated_at = ?, access_count = access_count + 1, "
            "confidence = MIN(confidence + 0.05, 1.0) WHERE fact_hash = ?",
            (ts, fact_hash)
        )
        conn.commit()
        return {"status": "updated", "id": existing["id"], "fact": fact}
    else:
        cursor = conn.execute(
            "INSERT INTO knowledge (chat_id, category, key_topic, fact, confidence, source, "
            "created_at, updated_at, fact_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (chat_id, category, key_topic, fact, confidence, source, ts, ts, fact_hash)
        )
        # Update FTS index — non-fatal if it fails
        try:
            conn.execute("INSERT INTO knowledge_fts(rowid, fact, key_topic, category) VALUES (?, ?, ?, ?)",
                        (cursor.lastrowid, fact, key_topic, category))
        except Exception as fts_err:
            import logging
            logging.getLogger("brain").warning("FTS sync failed for fact %d: %s", cursor.lastrowid, fts_err)
        conn.commit()
        return {"status": "created", "id": cursor.lastrowid, "fact": fact}

def search_facts(chat_id: str, query: str = None, category: str = None,
                 limit: int = 10) -> list[dict]:
    """Search knowledge base. Uses FTS for text search."""
    conn = get_db()
    if query:
        try:
            rows = conn.execute(
                "SELECT k.* FROM knowledge k JOIN knowledge_fts f ON k.id = f.rowid "
                "WHERE k.chat_id = ? AND knowledge_fts MATCH ? "
                "ORDER BY k.confidence DESC, k.access_count DESC LIMIT ?",
                (chat_id, query, limit)
            ).fetchall()
        except Exception:
            # FTS may be out of sync; fallback to LIKE search
            rows = conn.execute(
                "SELECT * FROM knowledge WHERE chat_id = ? AND fact LIKE ? "
                "ORDER BY confidence DESC, access_count DESC LIMIT ?",
                (chat_id, f"%{query}%", limit)
            ).fetchall()
    elif category:
        rows = conn.execute(
            "SELECT * FROM knowledge WHERE chat_id = ? AND category = ? "
            "ORDER BY confidence DESC, access_count DESC LIMIT ?",
            (chat_id, category, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM knowledge WHERE chat_id = ? "
            "ORDER BY confidence DESC, last_accessed DESC LIMIT ?",
            (chat_id, limit)
        ).fetchall()

    # Update access tracking
    if rows:
        ids = [r["id"] for r in rows]
        conn.execute(
            f"UPDATE knowledge SET last_accessed = ?, access_count = access_count + 1 "
            f"WHERE id IN ({','.join('?' * len(ids))})",
            [now_utc()] + ids
        )
        conn.commit()
    return [dict(r) for r in rows]

def get_relevant_facts(chat_id: str, message: str, limit: int = 8) -> list[dict]:
    """Get most relevant facts for a given message (for context injection)."""
    # Extract key nouns/topics from message (simple keyword extraction)
    words = re.findall(r'\b[a-z]{4,}\b', message.lower())
    stopwords = {'that', 'this', 'with', 'have', 'from', 'they', 'will', 'what', 'your', 'just', 'into', 'more', 'when', 'than', 'some', 'time'}
    keywords = [w for w in set(words) if w not in stopwords][:5]

    results = []
    if keywords:
        query = " OR ".join(keywords)
        try:
            results = search_facts(chat_id, query=query, limit=limit)
        except Exception:
            pass

    # Pad with top-confidence facts if fewer than limit
    if len(results) < limit:
        existing_ids = {r["id"] for r in results}
        general = search_facts(chat_id, limit=limit)
        for f in general:
            if f["id"] not in existing_ids:
                results.append(f)
            if len(results) >= limit:
                break

    return results[:limit]

# ── Layer 4: Episodic search ─────────────────────────────────────────────────
def search_history(query: str, chat_id: str = None, limit: int = 10) -> list[dict]:
    """Full-text search over all episodic history."""
    with get_db() as conn:
        if chat_id:
            rows = conn.execute(
                "SELECT e.* FROM episodes e JOIN episodes_fts f ON e.id = f.rowid "
                "WHERE e.chat_id = ? AND episodes_fts MATCH ? ORDER BY e.timestamp DESC LIMIT ?",
                (chat_id, query, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT e.* FROM episodes e JOIN episodes_fts f ON e.id = f.rowid "
                "WHERE episodes_fts MATCH ? ORDER BY e.timestamp DESC LIMIT ?",
                (query, limit)
            ).fetchall()
    return [dict(r) for r in rows]

# ── Layer 5: Reflective Memory ──────────────────────────────────────────────
def get_daily_log_content(chat_id: str, date_str: str = None) -> str:
    """Read today's daily log (or a specific date)."""
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")
    log_file = DAILY_DIR / f"{date_str}.md"
    if log_file.exists():
        return log_file.read_text()
    return ""

def save_reflection(chat_id: str, summary: str, message_count: int, facts_extracted: int = 0):
    """Save a daily reflection summary."""
    ts = now_utc()
    date_str = datetime.now().strftime("%Y-%m-%d")
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO reflections (chat_id, reflection_date, summary, "
            "message_count, facts_extracted, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (chat_id, date_str, summary, message_count, facts_extracted, ts)
        )
        conn.commit()

def update_memory_md(facts_text: str, section: str = "Recent Learnings"):
    """Update the curated MEMORY.md file with new facts."""
    if not MEMORY_MD.parent.exists():
        MEMORY_MD.parent.mkdir(parents=True)

    if MEMORY_MD.exists():
        content = MEMORY_MD.read_text()
    else:
        content = "# Ronku's Memory\n\n*Curated by the reflection system. Human-readable and git-trackable.*\n\n"

    # Update or add section
    section_header = f"## {section}"
    date_str = datetime.now().strftime("%Y-%m-%d")

    if section_header in content:
        # Replace the section
        parts = content.split(section_header)
        # Find end of section (next ##)
        after = parts[1]
        next_section = after.find("\n## ")
        if next_section > 0:
            rest = after[next_section:]
        else:
            rest = ""
        content = parts[0] + section_header + "\n\n" + f"*Updated: {date_str}*\n\n" + facts_text + "\n" + rest
    else:
        content += f"\n{section_header}\n\n*Updated: {date_str}*\n\n{facts_text}\n"

    MEMORY_MD.write_text(content)

def get_memory_md() -> str:
    """Load the curated MEMORY.md content."""
    if MEMORY_MD.exists():
        return MEMORY_MD.read_text()[:3000]  # Limit to avoid token bloat
    return ""

# ── Mood tracking ──────────────────────────────────────────────────────────
def log_mood(chat_id: str, mood: str, confidence: float = 0.5, trigger: str = None):
    """Log a mood observation."""
    with get_db() as conn:
        conn.execute(
            "INSERT INTO mood_log (chat_id, mood, confidence, detected_at, trigger) VALUES (?, ?, ?, ?, ?)",
            (chat_id, mood, confidence, now_utc(), trigger)
        )
        conn.commit()

def get_current_mood(chat_id: str) -> Optional[dict]:
    """Get most recent mood for a chat."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT mood, confidence, detected_at FROM mood_log WHERE chat_id = ? "
            "ORDER BY detected_at DESC LIMIT 1",
            (chat_id,)
        ).fetchone()
    return dict(row) if row else None

# ── Context assembly (the main function n8n calls) ──────────────────────────
def assemble_context(chat_id: str, user_message: str) -> dict:
    """
    Build the full context payload for an AI call:
    - Soul system prompt
    - Relevant facts from knowledge base
    - Recent messages (working memory)
    - MEMORY.md excerpt
    - Current mood
    - Relevant past episodes (Phase 4: episodic retrieval)
    - Unapplied reflection lessons (Phase 4: lesson injection)
    """
    soul = load_soul()
    soul_prompt = soul_to_system_prompt(soul)
    facts = get_relevant_facts(chat_id, user_message, limit=8)
    messages = get_context_messages(chat_id, limit=50)
    memory_md = get_memory_md()
    mood = get_current_mood(chat_id)

    # ── Phase 4: Episodic retrieval ──────────────────────────────────────────
    conn = get_db()
    relevant_episodes: list[dict] = []
    try:
        ep_rows = conn.execute(
            "SELECT situation, outcome, tools_used FROM episodes "
            "WHERE chat_id = ? AND situation IS NOT NULL "
            "AND situation MATCH ? "
            "ORDER BY rowid DESC LIMIT 3",
            (chat_id, user_message[:100])
        ).fetchall()
        relevant_episodes = [dict(r) for r in ep_rows]
    except Exception:
        # FTS may not be available on the episodes table — fall back silently
        pass

    # ── Phase 4: Reflection lesson injection ────────────────────────────────
    unapplied_lessons: list[dict] = []
    try:
        lesson_rows = conn.execute(
            "SELECT id, lesson, category FROM reflections "
            "WHERE chat_id = ? AND lesson IS NOT NULL AND applied = 0 "
            "ORDER BY reflection_date DESC LIMIT 3",
            (chat_id,)
        ).fetchall()
        unapplied_lessons = [dict(r) for r in lesson_rows]
        if unapplied_lessons:
            ids = [str(r["id"]) for r in unapplied_lessons]
            conn.execute(
                f"UPDATE reflections SET applied = 1 WHERE id IN ({','.join(ids)})"
            )
            conn.commit()
    except Exception:
        pass

    # Build enriched system prompt
    system_parts = [soul_prompt]

    if memory_md:
        system_parts.append("\n## Your Memory (curated knowledge about owner)\n" + memory_md[:1500])

    if facts:
        facts_text = "\n".join([f"- [{f['category']}] {f['fact']}" for f in facts])
        system_parts.append(f"\n## Relevant Knowledge\n{facts_text}")

    if relevant_episodes:
        ep_lines = []
        for ep in relevant_episodes:
            tools = ep.get("tools_used", "")
            tool_note = f" (used: {tools})" if tools else ""
            outcome = ep.get("outcome", "completed")
            ep_lines.append(f"- Previously: \"{ep['situation'][:120]}\" → {outcome[:120]}{tool_note}")
        system_parts.append("\n## Relevant Past Episodes (learn from these)\n" + "\n".join(ep_lines))

    if unapplied_lessons:
        lesson_lines = [
            f"- [{r['category']}] {r['lesson']}"
            for r in unapplied_lessons
        ]
        system_parts.append(
            "\n## Self-Improvement Lessons (apply these in this conversation)\n"
            + "\n".join(lesson_lines)
        )

    if mood:
        system_parts.append(f"\n## Owner's current mood: {mood['mood']} (confidence: {mood['confidence']:.0%})")

    system_prompt = "\n".join(system_parts)

    # Tool awareness — describes the AI Agent's native HTTP tool format
    system_prompt += """

## Tools
You have access to an "execute" tool that runs actions on the owner's Mac.
Call it with: {"tool": "<name>", "args": {"chat_id": "<chatId>", ...args}}

Available tools:
- **shell** — `{"command": "..."}` — Run a safe shell command
- **file_read** — `{"path": "..."}` — Read a file
- **file_write** — `{"path": "...", "content": "..."}` — Write a file
- **notify** — `{"title": "...", "message": "..."}` — macOS notification
- **open_url** — `{"url": "..."}` — Open URL in browser
- **osascript** — `{"script": "..."}` — Run AppleScript
- **brain_note** — `{"fact": "...", "category": "preference|fact|habit|context"}` — Remember a fact
- **brain_recall** — `{"query": "..."}` — Search memory
- **brain_stats** — `{}` — Brain statistics
- **brain_new_session** — `{}` — Start fresh conversation window

Use tools proactively. Don't ask "should I check your disk?" — just do it.
Always include chat_id in args for brain tools.
"""

    # ── Thinking Protocol ──────────────────────────────────────────────────
    system_prompt += """

## Thinking Protocol
Before EVERY response, you MUST output your reasoning inside <think>...</think> tags.
This thinking block is shown to the user as a translucent "thinking" bubble — it makes you feel alive and transparent.

Rules:
1. ALWAYS start your response with <think>...</think> — never skip it
2. Keep it concise: 1-3 sentences max
3. Include: what the user wants, whether you need tools, your plan
4. After </think>, write your normal response

Examples:
- <think>Rohan wants to know his disk space. I'll run df -h to check.</think>
- <think>Simple greeting — no tools needed, just a warm reply.</think>
- <think>He's asking about his schedule. I should check if there are any TODOs due today using brain_recall.</think>

The <think> block will be stripped from your final message and shown separately. Your response after </think> should NOT reference or repeat the thinking.
"""

    return {
        "system_prompt": system_prompt,
        "messages": messages,
        "soul": soul,
        "facts_count": len(facts),
        "message_count": len(messages),
        "mood": mood,
        "episodes_injected": len(relevant_episodes),
        "lessons_injected": len(unapplied_lessons),
    }


# ── Daily log helper ────────────────────────────────────────────────────────
def _append_daily_log(chat_id: str, role: str, content: str, ts: str):
    """Append message to today's daily Markdown log."""
    try:
        date_str = ts[:10]
        log_file = DAILY_DIR / f"{date_str}.md"
        icon = "👤" if role == "user" else ("🤖" if role == "assistant" else "🔧")
        line = f"\n**{ts[11:16]} UTC** {icon} *{role}*\n{content[:500]}\n\n---"
        # Check existence BEFORE opening (avoids the race where open('a') creates the file)
        needs_header = not log_file.exists()
        with open(log_file, "a") as f:
            if needs_header:
                f.write(f"# Chat Log — {date_str}\n\nchat_id: {chat_id}\n\n---")
            f.write(line)
    except Exception:
        pass  # Daily log is non-critical; never break the main flow

# ── Stats ───────────────────────────────────────────────────────────────────
def get_stats(chat_id: str) -> dict:
    """Return brain statistics."""
    conn = get_db()
    wm = conn.execute("SELECT COUNT(*) as n FROM working_memory WHERE chat_id = ?", (chat_id,)).fetchone()["n"]
    kn = conn.execute("SELECT COUNT(*) as n FROM knowledge WHERE chat_id = ?", (chat_id,)).fetchone()["n"]
    ep = conn.execute("SELECT COUNT(*) as n FROM episodes WHERE chat_id = ?", (chat_id,)).fetchone()["n"]
    rf = conn.execute("SELECT COUNT(*) as n FROM reflections WHERE chat_id = ?", (chat_id,)).fetchone()["n"]
    oldest = conn.execute("SELECT MIN(timestamp) as t FROM episodes WHERE chat_id = ?", (chat_id,)).fetchone()["t"]

    db_size = BRAIN_DB.stat().st_size if BRAIN_DB.exists() else 0
    md_size = sum(f.stat().st_size for f in DAILY_DIR.glob("*.md"))

    # Last backup timestamp
    last_backup = None
    if BACKUPS_DIR.exists():
        backups = sorted(BACKUPS_DIR.glob("brain-*.db"), reverse=True)
        if backups:
            last_backup = backups[0].name.replace("brain-", "").replace(".db", "")

    return {
        "working_messages": wm,
        "knowledge_facts": kn,
        "episode_count": ep,
        "reflections": rf,
        "oldest_memory": oldest,
        "db_size_kb": round(db_size / 1024, 1),
        "daily_logs_kb": round(md_size / 1024, 1),
        "last_backup": last_backup,
        "memory_md_exists": MEMORY_MD.exists(),
        "brain_dir": str(BRAIN_DIR),
        "soul_file": str(SOUL_FILE),
    }

# ── WAL checkpoint ──────────────────────────────────────────────────────────
def wal_checkpoint():
    """Force a WAL checkpoint to compact the database."""
    conn = get_db()
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    return True

# ── Daily reflection (mem0/OpenClaw-style) ──────────────────────────────────
def run_daily_reflection(chat_id: str):
    """Summarize today's conversations, extract facts, update MEMORY.md."""
    import logging
    log = logging.getLogger("brain")

    date_str = datetime.now().strftime("%Y-%m-%d")
    daily_log = get_daily_log_content(chat_id, date_str)
    if not daily_log or len(daily_log) < 50:
        log.info("Reflection: no substantial daily log for %s", date_str)
        return {"status": "skipped", "reason": "no data"}

    # Get today's messages from episodic log
    conn = get_db()
    today_start = f"{date_str}T00:00:00"
    rows = conn.execute(
        "SELECT direction, substr(content,1,300) as content FROM episodes "
        "WHERE chat_id = ? AND timestamp >= ? ORDER BY timestamp",
        (chat_id, today_start)
    ).fetchall()

    if len(rows) < 2:
        log.info("Reflection: too few messages (%d) for %s", len(rows), date_str)
        return {"status": "skipped", "reason": "too few messages"}

    # Build summary from existing messages (no external AI call needed)
    user_msgs = [r["content"] for r in rows if r["direction"] == "inbound"]
    ai_msgs = [r["content"] for r in rows if r["direction"] == "outbound"]

    summary_parts = []
    summary_parts.append(f"**{date_str}** — {len(rows)} messages ({len(user_msgs)} user, {len(ai_msgs)} bot)")
    
    # Extract key topics from user messages
    topics = set()
    for msg in user_msgs:
        # Simple keyword extraction — pull significant words
        words = [w.strip(".,!?\"'") for w in msg.lower().split() if len(w) > 4]
        topics.update(words[:5])
    
    if topics:
        summary_parts.append(f"Topics: {', '.join(list(topics)[:10])}")
    
    summary = "\n".join(summary_parts)
    
    # Save reflection to DB
    save_reflection(chat_id, summary, len(rows), facts_extracted=0)

    # Get ALL facts for MEMORY.md update
    all_facts = search_facts(chat_id, limit=50)
    if all_facts:
        facts_md = "\n".join([f"- [{f['category']}] {f['fact']}" for f in all_facts])
        update_memory_md(facts_md, section="Known Facts")

    # Add daily summary to MEMORY.md
    update_memory_md(summary, section="Recent Activity")

    log.info("Reflection complete: %d messages, %d facts in MEMORY.md", len(rows), len(all_facts))
    return {"status": "ok", "messages": len(rows), "facts": len(all_facts)}


def bootstrap_memory_md(chat_id: str):
    """Bootstrap MEMORY.md from existing DB content (run once)."""
    import logging
    log = logging.getLogger("brain")

    soul = load_soul()
    facts = search_facts(chat_id, limit=100)
    stats = get_stats(chat_id)

    content = "# Ronku's Memory\n\n"
    content += "*Curated by the reflection system. Human-readable and git-trackable.*\n\n"

    # Owner section from soul
    ctx = soul.get("context", {})
    content += "## Owner: Rohan\n"
    content += f"- Timezone: {ctx.get('owner_timezone', 'Unknown')}\n"
    content += f"- Location: {ctx.get('owner_location', 'Unknown')}\n"
    content += f"- Machine: {ctx.get('primary_machine', 'Unknown')}\n"
    content += f"- Languages: {ctx.get('preferred_language', 'Unknown')}\n\n"

    # Known facts
    if facts:
        content += "## Known Facts\n\n"
        content += f"*{len(facts)} facts stored*\n\n"
        for f in facts:
            content += f"- [{f['category']}] {f['fact']}\n"
        content += "\n"

    # Stats
    content += "## Brain Stats\n\n"
    content += f"- Total episodes: {stats['episode_count']}\n"
    content += f"- Working memory: {stats['working_messages']} messages\n"
    content += f"- Knowledge base: {stats['knowledge_facts']} facts\n"
    content += f"- DB size: {stats['db_size_kb']} KB\n"
    content += f"- First memory: {stats['oldest_memory']}\n"

    MEMORY_MD.write_text(content)
    log.info("MEMORY.md bootstrapped (%d bytes)", len(content))
    return {"status": "ok", "size": len(content)}


# ── Extract facts from conversation (mem0-style) ────────────────────────────
def extract_facts_prompt(recent_messages: list[dict]) -> str:
    """Build a prompt for the AI to extract memorable facts from a conversation."""
    conversation = "\n".join([
        f"{m['role'].upper()}: {m['content'][:200]}"
        for m in recent_messages[-10:]
    ])
    return f"""Review this conversation and extract any facts worth remembering about the user.
Focus on: preferences, habits, personal details, project context, repeated topics.
Ignore: greetings, transient requests, tool call results.

CONVERSATION:
{conversation}

Respond ONLY with a JSON array (empty array if nothing worth storing):
[
  {{"fact": "...", "category": "preference|fact|habit|context|relationship|skill", "key_topic": "...", "confidence": 0.0-1.0}},
  ...
]"""


# ── Todo CRUD ────────────────────────────────────────────────────────────────
def create_todo(chat_id: str, task: str, due_at: str = None,
                remind_at: str = None, recurrence: str = None) -> dict:
    """Create a new TODO item."""
    ts = now_utc()
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO todos (chat_id, task, due_at, remind_at, recurrence, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (chat_id, task, due_at, remind_at, recurrence, ts)
    )
    conn.commit()
    return {"id": cursor.lastrowid, "task": task, "due_at": due_at, "remind_at": remind_at}


def get_todos(chat_id: str, completed: bool = False,
             due_today: bool = False, due_soon_minutes: int = None) -> list[dict]:
    """Fetch todos with optional filters."""
    conn = get_db()
    query = "SELECT * FROM todos WHERE chat_id = ? AND completed = ?"
    params: list = [chat_id, 1 if completed else 0]

    if due_today:
        today = datetime.now().strftime("%Y-%m-%d")
        query += " AND due_at LIKE ?"
        params.append(f"{today}%")

    if due_soon_minutes:
        cutoff = (datetime.now(timezone.utc) + timedelta(minutes=due_soon_minutes)).isoformat()
        query += " AND remind_at IS NOT NULL AND remind_at <= ? AND reminder_sent = 0"
        params.append(cutoff)

    query += " ORDER BY due_at ASC, created_at ASC"
    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def update_todo(todo_id: int, **kwargs) -> bool:
    """Update specific fields of a todo."""
    allowed = {"completed", "reminder_sent", "due_at", "remind_at", "task"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return False
    conn = get_db()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    conn.execute(f"UPDATE todos SET {set_clause} WHERE id = ?",
                 list(updates.values()) + [todo_id])
    conn.commit()
    return True


# ── Alert suppression ────────────────────────────────────────────────────────
def should_alert(alert_type: str) -> bool:
    """Return True if enough time has passed since last alert of this type."""
    conn = get_db()
    row = conn.execute(
        "SELECT last_alerted, suppression_hours FROM alerts WHERE alert_type = ?",
        (alert_type,)
    ).fetchone()
    if not row or not row["last_alerted"]:
        return True
    last = datetime.fromisoformat(row["last_alerted"])
    hours = row["suppression_hours"] or 4
    return (datetime.now(timezone.utc) - last).total_seconds() > hours * 3600


def ack_alert(alert_type: str):
    """Record that an alert was sent (sets last_alerted to now)."""
    conn = get_db()
    conn.execute(
        "INSERT INTO alerts (alert_type, last_alerted) VALUES (?, ?) "
        "ON CONFLICT(alert_type) DO UPDATE SET last_alerted = excluded.last_alerted",
        (alert_type, now_utc())
    )
    conn.commit()


# ── Nightly: merged reflection + journal ─────────────────────────────────────
def run_nightly(chat_id: str) -> dict:
    """
    Single nightly function: one Groq LLM call producing both
    a reflection (lesson + category) and a journal entry (patterns + improvements).
    Replaces run_daily_reflection() for production use.
    """
    import logging, httpx
    log = logging.getLogger("brain")

    date_str = datetime.now().strftime("%Y-%m-%d")
    today_start = f"{date_str}T00:00:00"
    conn = get_db()
    rows = conn.execute(
        "SELECT direction, substr(content,1,400) as content FROM episodes "
        "WHERE chat_id = ? AND timestamp >= ? ORDER BY timestamp",
        (chat_id, today_start)
    ).fetchall()

    if len(rows) < 3:
        log.info("Nightly: too few messages (%d) — skipping", len(rows))
        return {"status": "skipped", "reason": "too few messages", "count": len(rows)}

    convo = "\n".join([
        f"{'USER' if r['direction'] == 'inbound' else 'BOT'}: {r['content']}"
        for r in rows
    ])
    prompt = f"""You are reviewing today's conversations for ronku_bot (a personal AI assistant). Date: {date_str}.

CONVERSATIONS:
{convo[:3000]}

Output ONLY valid JSON (no markdown):
{{
  "reflection": {{
    "summary": "2-3 sentence summary of today",
    "lesson": "one concrete thing to do better next time",
    "category": "tool_use|communication|knowledge|memory"
  }},
  "journal": {{
    "entry": "reflective first-person diary entry (3-5 sentences)",
    "patterns": ["pattern1", "pattern2"],
    "improvements": ["improvement1"]
  }}
}}"""

    groq_key = os.environ.get("GROQ_API_KEY", "")
    if not groq_key:
        log.warning("Nightly: GROQ_API_KEY not set — falling back to basic reflection")
        return run_daily_reflection(chat_id)

    result = {"status": "ok", "date": date_str, "message_count": len(rows)}
    try:
        resp = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 600,
                "temperature": 0.3,
            },
            timeout=30.0,
        )
        content = resp.json()["choices"][0]["message"]["content"]
        # Strip markdown fences if present
        content = content.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        data = json.loads(content)

        ref = data.get("reflection", {})
        jrn = data.get("journal", {})

        # Save reflection with new AI fields
        ts = now_utc()
        conn.execute(
            "INSERT OR REPLACE INTO reflections "
            "(chat_id, reflection_date, summary, message_count, facts_extracted, lesson, category, applied, created_at) "
            "VALUES (?, ?, ?, ?, 0, ?, ?, 0, ?)",
            (chat_id, date_str, ref.get("summary", ""), len(rows),
             ref.get("lesson"), ref.get("category"), ts)
        )
        # Save journal entry
        conn.execute(
            "INSERT OR REPLACE INTO inner_journal (date, entry, patterns, improvements, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (date_str, jrn.get("entry"),
             json.dumps(jrn.get("patterns", [])),
             json.dumps(jrn.get("improvements", [])), ts)
        )
        conn.commit()

        # Update MEMORY.md
        update_memory_md(ref.get("summary", ""), section="Recent Activity")
        if ref.get("lesson"):
            update_memory_md(f"- [{ref.get('category','general')}] {ref['lesson']}",
                             section="Lessons Learned")

        result.update({"reflection": ref, "journal": jrn})
        log.info("Nightly complete: %d messages, lesson: %s", len(rows), ref.get("lesson", "")[:80])

    except Exception as e:
        log.error("Nightly LLM call failed: %s — falling back to basic reflection", e)
        result = run_daily_reflection(chat_id)
        result["warning"] = "LLM call failed, used keyword fallback"

    return result


# ── Memory consolidation (simple) ────────────────────────────────────────────
def run_memory_consolidation(chat_id: str) -> dict:
    """
    Simple consolidation:
    1. Prune facts with confidence < 0.3, access_count = 0, older than 30 days
    2. Merge facts with identical key_topic (keep highest confidence)
    3. WAL checkpoint
    """
    import logging
    log = logging.getLogger("brain")
    conn = get_db()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

    # Step 1: Prune stale low-confidence facts
    pruned = conn.execute(
        "DELETE FROM knowledge WHERE chat_id = ? AND confidence < 0.3 "
        "AND access_count = 0 AND created_at < ?",
        (chat_id, cutoff)
    ).rowcount

    # Step 2: For each key_topic with >3 facts, keep top 3 by confidence
    topics = conn.execute(
        "SELECT key_topic, COUNT(*) as n FROM knowledge WHERE chat_id = ? "
        "GROUP BY key_topic HAVING n > 3",
        (chat_id,)
    ).fetchall()
    merged = 0
    for t in topics:
        topic = t["key_topic"]
        # Get IDs beyond the top 3
        to_keep = conn.execute(
            "SELECT id FROM knowledge WHERE chat_id = ? AND key_topic = ? "
            "ORDER BY confidence DESC, access_count DESC LIMIT 3",
            (chat_id, topic)
        ).fetchall()
        keep_ids = [r["id"] for r in to_keep]
        placeholders = ",".join("?" * len(keep_ids))
        deleted = conn.execute(
            f"DELETE FROM knowledge WHERE chat_id = ? AND key_topic = ? "
            f"AND id NOT IN ({placeholders})",
            [chat_id, topic] + keep_ids
        ).rowcount
        merged += deleted

    conn.commit()
    wal_checkpoint()

    log.info("Consolidation: pruned=%d, merged=%d", pruned, merged)
    return {"status": "ok", "pruned": pruned, "merged": merged}


# ── CLI mode ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys, logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

    OWNER_CHAT_ID = get_owner_chat_id()

    if "--nightly" in sys.argv:
        result = run_nightly(OWNER_CHAT_ID)
        print(json.dumps(result, indent=2))
    elif "--reflect" in sys.argv:
        result = run_daily_reflection(OWNER_CHAT_ID)
        print(json.dumps(result, indent=2))
    elif "--consolidate" in sys.argv:
        result = run_memory_consolidation(OWNER_CHAT_ID)
        print(json.dumps(result, indent=2))
    elif "--bootstrap-memory" in sys.argv:
        result = bootstrap_memory_md(OWNER_CHAT_ID)
        print(json.dumps(result, indent=2))
    elif "--checkpoint" in sys.argv:
        wal_checkpoint()
        print("WAL checkpoint complete")
    elif "--stats" in sys.argv:
        stats = get_stats(OWNER_CHAT_ID)
        print(json.dumps(stats, indent=2))
    else:
        print("Usage: brain.py [--nightly|--reflect|--consolidate|--bootstrap-memory|--checkpoint|--stats]")
