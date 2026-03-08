#!/bin/bash
# install.sh — Install mac-agent as a macOS LaunchAgent (auto-start on login)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_NAME="com.ronkbot.mac-agent"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"
VENV_DIR="$SCRIPT_DIR/.venv"

echo "🖥️  Installing ronkbot mac-agent..."

# 1. Create venv if needed
if [ ! -d "$VENV_DIR" ]; then
    echo "  📦 Creating Python virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

# 2. Install dependencies
echo "  📦 Installing dependencies..."
"$VENV_DIR/bin/pip" install -q -r "$SCRIPT_DIR/requirements.txt"

# 3. Create LaunchAgent plist
echo "  📝 Creating LaunchAgent: $PLIST_PATH"

# Make the wrapper executable
chmod +x "$SCRIPT_DIR/launch-agent-wrapper.sh"

cat > "$PLIST_PATH" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_NAME}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>${SCRIPT_DIR}/launch-agent-wrapper.sh</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${HOME}/.ronkbot/agent-stdout.log</string>
    <key>StandardErrorPath</key>
    <string>${HOME}/.ronkbot/agent-stderr.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
PLIST

# 4. Load the agent
echo "  🚀 Loading LaunchAgent..."
launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load "$PLIST_PATH"

# 5. Verify
sleep 2
if curl -s http://127.0.0.1:4242/health | grep -q '"status":"ok"'; then
    echo "  ✅ mac-agent is running on http://127.0.0.1:4242"
    echo ""
    echo "  Manage:"
    echo "    Stop:    launchctl unload $PLIST_PATH"
    echo "    Start:   launchctl load $PLIST_PATH"
    echo "    Logs:    tail -f ~/.ronkbot/agent.log"
    echo "    Uninstall: rm $PLIST_PATH && launchctl unload $PLIST_PATH"
else
    echo "  ⚠️  Agent may not be running. Check: tail ~/.ronkbot/agent-stderr.log"
fi
