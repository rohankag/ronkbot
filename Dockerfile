FROM n8nio/n8n:1.82.1

LABEL maintainer="rohankag"
LABEL description="Personal AI Assistant — Telegram + n8n + Gemini"
LABEL org.opencontainers.image.source="https://github.com/rohankag/ronkbot"
LABEL org.opencontainers.image.licenses="MIT"

USER root
# Pull the docker CLI binary from the official minimal docker image
# (n8n has no package manager so we copy the binary directly)
COPY --from=docker:cli /usr/local/bin/docker /usr/local/bin/docker

USER node

# Copy pre-built workflows so they're available inside the container without
# needing a host volume mount. Users who want to customise workflows can still
# override by mounting their own directory at /home/node/.n8n/workflows.
COPY --chown=node:node n8n-workflows/ /home/node/.n8n/workflows/

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD wget -q --spider http://localhost:5678/healthz || exit 1

# Expose n8n port
EXPOSE 5678

# Inherit entrypoint from parent image:  tini -- /docker-entrypoint.sh
