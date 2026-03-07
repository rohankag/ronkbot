#!/bin/bash
# ronkbot n8n entrypoint
# Starts n8n and auto-imports workflows + credentials on first run
set -e

N8N_DIR="${HOME}/.n8n"
FLAG_FILE="${N8N_DIR}/.setup_complete"

# Start n8n in the background so we can interact with its CLI
/docker-entrypoint.sh &
N8N_PID=$!

# Wait for n8n to be ready
echo "[entrypoint] Waiting for n8n to start..."
for _ in $(seq 1 60); do
    if wget -q --spider http://localhost:5678/healthz 2>/dev/null; then
        echo "[entrypoint] n8n is ready!"
        break
    fi
    sleep 1
done

if [ ! -f "$FLAG_FILE" ]; then
    echo "[entrypoint] First run — importing workflows and creating credentials..."
    
    # Import all 3 core workflows using n8n CLI
    for wf in /home/node/.n8n/workflows/01-telegram-listener.json \
               /home/node/.n8n/workflows/02-gemini-chat.json \
               /home/node/.n8n/workflows/03-command-handler.json; do
        if [ -f "$wf" ]; then
            echo "[entrypoint] Importing $wf..."
            n8n import:workflow --input="$wf" --separate || echo "[entrypoint] WARNING: Failed to import $wf"
        fi
    done
    
    touch "$FLAG_FILE"
    echo "[entrypoint] Setup complete. Please configure credentials in the n8n UI."
fi

# Keep running
wait $N8N_PID
