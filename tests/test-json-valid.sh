#!/usr/bin/env bash
# Test: all n8n workflow JSON files are valid JSON

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
WORKFLOWS_DIR="${REPO_ROOT}/n8n-workflows"

PASS=0
FAIL=0
ERRORS=()

echo "==> Validating n8n workflow JSON files in: ${WORKFLOWS_DIR}"

if [ ! -d "${WORKFLOWS_DIR}" ]; then
    echo "FAIL: workflows directory not found: ${WORKFLOWS_DIR}"
    exit 1
fi

for f in "${WORKFLOWS_DIR}"/*.json; do
    if [ ! -f "${f}" ]; then
        echo "WARN: No JSON files found in ${WORKFLOWS_DIR}"
        break
    fi
    filename="$(basename "${f}")"
    if jq empty "${f}" 2>/dev/null; then
        echo "  PASS: ${filename}"
        PASS=$((PASS + 1))
    else
        echo "  FAIL: ${filename} — invalid JSON"
        ERRORS+=("${filename}")
        FAIL=$((FAIL + 1))
    fi
done

echo ""
echo "Results: ${PASS} passed, ${FAIL} failed"

if [ "${FAIL}" -gt 0 ]; then
    echo ""
    echo "Failed files:"
    for e in "${ERRORS[@]}"; do
        echo "  - ${e}"
    done
    exit 1
fi

echo "All workflow JSON files are valid."
