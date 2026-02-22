#!/usr/bin/env bash
# Run all CI tests for ronkbot
# Usage: ./tests/run-tests.sh [--skip-docker]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKIP_DOCKER=false

for arg in "$@"; do
    case "${arg}" in
        --skip-docker) SKIP_DOCKER=true ;;
    esac
done

PASS=0
FAIL=0

run_test() {
    local name="$1"
    local script="$2"

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Running: ${name}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    if bash "${script}"; then
        echo ""
        echo "  ✓ ${name} — PASSED"
        PASS=$((PASS + 1))
    else
        echo ""
        echo "  ✗ ${name} — FAILED"
        FAIL=$((FAIL + 1))
    fi
}

echo "╔══════════════════════════════════════════════╗"
echo "║          ronkbot CI Test Suite               ║"
echo "╚══════════════════════════════════════════════╝"

run_test "JSON Validation"         "${SCRIPT_DIR}/test-json-valid.sh"
run_test "ShellCheck Lint"         "${SCRIPT_DIR}/test-shellcheck.sh"

if [ "${SKIP_DOCKER}" = "false" ]; then
    run_test "Docker Build"        "${SCRIPT_DIR}/test-docker-build.sh"
else
    echo ""
    echo "  SKIP: Docker Build (--skip-docker flag set)"
fi

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "  Final Results: ${PASS} passed, ${FAIL} failed"
echo "╚══════════════════════════════════════════════╝"

if [ "${FAIL}" -gt 0 ]; then
    exit 1
fi
