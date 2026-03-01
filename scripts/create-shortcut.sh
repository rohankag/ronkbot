#!/usr/bin/env bash
# create-shortcut.sh
# Creates a macOS Shortcut named "Start ronkbot" that starts the Docker container.
# After creation, the Shortcut syncs to your iPhone automatically via iCloud.

set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-$HOME/.ronkbot}"
SHORTCUT_NAME="Start ronkbot"

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'
BOLD='\033[1m'

echo ""
echo "${CYAN}╔══════════════════════════════════════════════════╗${NC}"
echo "${CYAN}║${NC}  📱 ${BOLD}ronkbot — iPhone Remote Start Setup${NC}          ${CYAN}║${NC}"
echo "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
echo ""

# ─── Option 1: use 'shortcuts' CLI (macOS 12+) ────────────────────────────────
create_via_shortcuts_cli() {
  echo "Creating Shortcut via shortcuts CLI..."

  # Build the AppleScript that will create the shortcut via Shortcuts app
  local applescript
  applescript=$(cat <<'APPLESCRIPT'
tell application "Shortcuts Events"
  set newShortcut to make new shortcut with properties {name:"Start ronkbot"}
  tell newShortcut
    make new action with properties {name:"Run Shell Script", parameters:{script:"cd ~/.ronkbot && docker compose up -d 2>&1 | tail -3"}}
  end tell
end tell
APPLESCRIPT
)

  if osascript -e "$applescript" 2>/dev/null; then
    echo -e "${GREEN}✓ Shortcut created: '${SHORTCUT_NAME}'${NC}"
    return 0
  fi
  return 1
}

# ─── Option 2: URL scheme deep-link (always works) ────────────────────────────
create_via_url_scheme() {
  echo ""
  echo "${YELLOW}⚠  Could not auto-create the Shortcut via CLI.${NC}"
  echo "   Opening Shortcuts app — please follow the steps below."
  echo ""

  echo "${BOLD}Manual steps (takes ~30 seconds):${NC}"
  echo "  1. In Shortcuts app: click  (+)  to create a new Shortcut"
  echo "  2. Name it:  ${CYAN}Start ronkbot${NC}"
  echo "  3. Search for action:  ${CYAN}Run Shell Script${NC}"
  echo "  4. Paste this command:"
  echo ""
  echo "     ${CYAN}cd ${INSTALL_DIR} && docker compose up -d${NC}"
  echo ""
  echo "  5. Click  ▶  to test it"
  echo "  6. The Shortcut will appear on your iPhone via iCloud automatically."
  echo ""

  open "shortcuts://" 2>/dev/null || true
}

# ─── Main ──────────────────────────────────────────────────────────────────────

# Check if Shortcuts app is available
if ! command -v shortcuts &>/dev/null && ! ls /Applications/Shortcuts.app &>/dev/null 2>&1; then
  echo "⚠  Shortcuts app not found. Make sure you are on macOS 12 (Monterey) or later."
  exit 1
fi

if create_via_shortcuts_cli; then
  :
else
  create_via_url_scheme
fi

echo ""
echo "${GREEN}${BOLD}✅ Next steps for iPhone:${NC}"
echo "  1. Open the ${BOLD}Shortcuts${NC} app on your iPhone"
echo "  2. You should see '${SHORTCUT_NAME}' synced via iCloud"
echo "  3. Long-press it → ${BOLD}Add to Home Screen${NC} for one-tap access"
echo "  4. Or add it as a ${BOLD}Home Screen widget${NC} via Edit Home Screen"
echo ""
echo "${CYAN}ℹ  Keep note: if your Mac is asleep, the Shortcut won't work.${NC}"
echo "   Use ${BOLD}Amphetamine${NC} (free on Mac App Store) to keep your Mac"
echo "   awake with the lid closed."
echo "   → https://apps.apple.com/us/app/amphetamine/id937984704"
echo ""
