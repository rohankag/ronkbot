FROM n8nio/n8n:latest

LABEL maintainer="ronkbot"
LABEL description="Personal AI Assistant with Telegram and Gemini"

# Install additional dependencies
USER root
RUN apk add --no-cache \
    sqlite \
    curl \
    jq

# Create app directory
WORKDIR /app

# Copy workflow files
COPY n8n-workflows /app/workflows
COPY scripts /app/scripts

# Set proper permissions
RUN chmod +x /app/scripts/*.sh

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD wget -q --spider http://localhost:5678/healthz || exit 1

# Expose n8n port
EXPOSE 5678

# Start n8n
USER node
CMD ["n8n"]
