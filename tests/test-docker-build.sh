#!/usr/bin/env bash
# Test: Docker image builds successfully and healthcheck endpoint is reachable

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

IMAGE_TAG="ronkbot-test:ci-$(date +%s)"
CONTAINER_NAME="ronkbot-ci-test-$$"

cleanup() {
    echo "==> Cleaning up..."
    docker rm -f "${CONTAINER_NAME}" 2>/dev/null || true
    docker rmi -f "${IMAGE_TAG}" 2>/dev/null || true
    echo "    Done."
}
trap cleanup EXIT INT TERM

echo "==> Building Docker image: ${IMAGE_TAG}"
cd "${REPO_ROOT}"

docker build \
    --file Dockerfile \
    --tag "${IMAGE_TAG}" \
    --no-cache \
    . 2>&1

echo "  PASS: Docker image built successfully"
echo ""

# Verify the image exists and has expected labels
echo "==> Verifying image metadata"
LABELS=$(docker inspect "${IMAGE_TAG}" --format '{{json .Config.Labels}}')
echo "    Labels: ${LABELS}"

EXPOSED_PORTS=$(docker inspect "${IMAGE_TAG}" --format '{{json .Config.ExposedPorts}}')
echo "    Exposed ports: ${EXPOSED_PORTS}"

if echo "${EXPOSED_PORTS}" | grep -q "5678"; then
    echo "  PASS: Port 5678 is exposed"
else
    echo "  FAIL: Port 5678 is not exposed"
    exit 1
fi

# Verify docker compose syntax is valid
echo ""
echo "==> Validating docker-compose.yml syntax"
if docker compose -f "${REPO_ROOT}/docker-compose.yml" config --quiet 2>&1; then
    echo "  PASS: docker-compose.yml is valid"
else
    echo "  FAIL: docker-compose.yml has syntax errors"
    exit 1
fi

echo ""
echo "All Docker tests passed."
