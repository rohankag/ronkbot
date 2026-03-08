#!/usr/bin/env bash
# backup.sh — Daily brain backup: local snapshot + iCloud + optional rclone to Google Drive
# Runs as a macOS LaunchAgent daily timer

set -euo pipefail

BRAIN_DIR="$HOME/.ronkbot/brain"
BACKUP_DIR="$BRAIN_DIR/backups"
DB_FILE="$BRAIN_DIR/brain.db"
LOG_FILE="$HOME/.ronkbot/backup.log"
DATE=$(date +%Y-%m-%d)
KEEP_DAYS=30

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

# ── Ensure dirs ──────────────────────────────────────────────────────────────
mkdir -p "$BACKUP_DIR"

log "🔄 Brain backup starting — $DATE"

# ── 1. Local timestamped snapshot ────────────────────────────────────────────
if [[ -f "$DB_FILE" ]]; then
  DEST="$BACKUP_DIR/brain-$DATE.db"
  cp "$DB_FILE" "$DEST"
  SIZE=$(du -sh "$DEST" | cut -f1)
  log "  ✅ Local snapshot: $DEST ($SIZE)"
else
  log "  ⚠️  brain.db not found, skipping local snapshot"
fi

# ── 2. iCloud Drive sync (zero-config, always-on) ────────────────────────────
ICLOUD_BRAIN="$HOME/Library/Mobile Documents/com~apple~CloudDocs/ronkbot-brain"
if [[ -d "$HOME/Library/Mobile Documents/com~apple~CloudDocs" ]]; then
  mkdir -p "$ICLOUD_BRAIN"
  # Sync entire brain directory (excluding large backups subfolder)
  rsync -a --exclude="backups/" --exclude="*.log" \
    "$BRAIN_DIR/" "$ICLOUD_BRAIN/" 2>/dev/null || true
  log "  ✅ iCloud sync complete: $ICLOUD_BRAIN"
else
  log "  ℹ️  iCloud Drive not available, skipping iCloud sync"
fi

# ── 3. Google Drive via rclone (optional, configure rclone first) ─────────────
RCLONE_REMOTE="${RCLONE_REMOTE:-gdrive}"  # Set in .env or environment
RCLONE_PATH="${RCLONE_PATH:-ronkbot-brain}"

if command -v rclone &>/dev/null && rclone listremotes 2>/dev/null | grep -q "^${RCLONE_REMOTE}:"; then
  if [[ -f "$DB_FILE" ]]; then
    rclone copy "$BACKUP_DIR/brain-$DATE.db" "${RCLONE_REMOTE}:${RCLONE_PATH}/db-backups/" \
      --log-level WARNING 2>&1 | tee -a "$LOG_FILE" || true
    log "  ✅ Google Drive backup: ${RCLONE_REMOTE}:${RCLONE_PATH}/db-backups/brain-$DATE.db"
  fi
  # Also sync MEMORY.md and daily logs to Drive
  rclone sync "$BRAIN_DIR/memory/" "${RCLONE_REMOTE}:${RCLONE_PATH}/memory/" \
    --log-level WARNING 2>&1 | tee -a "$LOG_FILE" || true
  log "  ✅ Google Drive memory sync complete"
else
  log "  ℹ️  rclone not configured (run: brew install rclone && rclone config)"
fi

# ── 4. Prune old local backups (keep last N days) ────────────────────────────
find "$BACKUP_DIR" -name "brain-*.db" -mtime +"$KEEP_DAYS" -delete 2>/dev/null || true
REMAINING=$(ls "$BACKUP_DIR"/brain-*.db 2>/dev/null | wc -l)
log "  🧹 Local backups: $REMAINING snapshots kept (${KEEP_DAYS}d retention)"

log "✅ Brain backup complete"
