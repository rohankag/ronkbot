FROM n8nio/n8n:latest

LABEL maintainer="ronkbot"
LABEL description="Personal AI Assistant with Telegram and Gemini"

# n8n runs as `node` user — no additional system packages needed.
# n8n's hardened image has apk removed; workflows and scripts are
# mounted via docker-compose volumes at runtime.

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD wget -q --spider http://localhost:5678/healthz || exit 1

# Expose n8n port
EXPOSE 5678

# Start n8n (default CMD from parent image — explicit here for clarity)
CMD ["n8n"]
