#!/usr/bin/env bash
# Test: shell scripts pass ShellCheck static analysis

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

PASS=0
FAIL=0
ERRORS=()

# Collect all shell scripts to lint
SHELL_FILES=(
    "${REPO_ROOT}/install.sh"
    "${REPO_ROOT}/scripts/backup.sh"
    "${REPO_ROOT}/scripts/start.sh"
    "${REPO_ROOT}/scripts/install.sh"
    "${REPO_ROOT}/tests/test-json-valid.sh"
    "${REPO_ROOT}/tests/test-shellcheck.sh"
    "${REPO_ROOT}/tests/test-docker-build.sh"
)

# Verify shellcheck is available
if ! command -v shellcheck &>/dev/null; then
    echo "FAIL: shellcheck not found. Install with: brew install shellcheck  OR  apt-get install shellcheck"
    exit 1
fi

echo "==> Running ShellCheck on shell scripts"
echo "    ShellCheck version: $(shellcheck --version | head -2 | tail -1)"
echo ""

for f in "${SHELL_FILES[@]}"; do
    if [ ! -f "${f}" ]; then
        echo "  SKIP: $(basename "${f}") — file not found"
        continue
    fi
    filename="$(basename "${f}")"
    if shellcheck --shell=bash --severity=warning "${f}"; then
        echo "  PASS: ${filename}"
        PASS=$((PASS + 1))
    else
        echo "  FAIL: ${filename}"
        ERRORS+=("${filename}")
        FAIL=$((FAIL + 1))
    fi
done

echo ""
echo "Results: ${PASS} passed, ${FAIL} failed"

if [ "${FAIL}" -gt 0 ]; then
    echo ""
    echo "ShellCheck failures in:"
    for e in "${ERRORS[@]}"; do
        echo "  - ${e}"
    done
    exit 1
fi

echo "All shell scripts pass ShellCheck."
