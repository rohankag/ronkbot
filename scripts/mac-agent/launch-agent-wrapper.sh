#!/bin/bash
# launch-agent-wrapper.sh — Sources .env then starts the mac-agent server.
# Used by the LaunchAgent plist so that server.py gets all env vars
# without baking secrets into the plist XML.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Source the project .env if it exists
if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    # shellcheck source=/dev/null
    source "$PROJECT_ROOT/.env"
    set +a
fi

# Start the server using the venv Python
exec "$SCRIPT_DIR/.venv/bin/python3" "$SCRIPT_DIR/server.py"
