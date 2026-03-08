#!/usr/bin/env bash
# test-system-workflow-structure.sh
# Structural tests for /system command integration

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CMD_HANDLER="${REPO_ROOT}/n8n-workflows/03-command-handler.json"
DOCS_DIR="${REPO_ROOT}/docs"
SCRIPTS_DIR="${REPO_ROOT}/scripts"

PASS=0; FAIL=0; ERRORS=()

assert_contains() {
  local label="$1" file="$2" query="$3" needle="$4"
  local result
  result="$(jq -r "${query}" "${file}" 2>/dev/null || echo "__ERR__")"
  if echo "${result}" | grep -qF "${needle}"; then
    echo "  PASS: ${label}"; PASS=$((PASS+1))
  else
    echo "  FAIL: ${label} (expected '${needle}', got '${result}')"; ERRORS+=("${label}"); FAIL=$((FAIL+1))
  fi
}

assert_file_exists() {
  local label="$1" path="$2"
  if [ -f "${path}" ]; then
    echo "  PASS: ${label}"; PASS=$((PASS+1))
  else
    echo "  FAIL: ${label} (file not found: ${path})"; ERRORS+=("${label}"); FAIL=$((FAIL+1))
  fi
}

assert_file_contains() {
  local label="$1" path="$2" needle="$3"
  if [ -f "${path}" ] && grep -qF "${needle}" "${path}"; then
    echo "  PASS: ${label}"; PASS=$((PASS+1))
  else
    echo "  FAIL: ${label} (needle '${needle}' not found in ${path})"; ERRORS+=("${label}"); FAIL=$((FAIL+1))
  fi
}

echo ""
echo "==> System Command Workflow Structure Tests"
echo ""

# ── Command handler routing ────────────────────────────────────────────────────
assert_contains "command handler has 'system' route"       "$CMD_HANDLER" '[.nodes[] | select(.name=="Route Command")] | .[0].parameters.rules.rules[].value' "system"
assert_contains "command handler has System Owner Check"   "$CMD_HANDLER" '[.nodes[].name] | .[]' "System Owner Check"
assert_contains "command handler has Route System Subcommand" "$CMD_HANDLER" '[.nodes[].name] | .[]' "Route System Subcommand"
assert_contains "command handler has Docker Status"        "$CMD_HANDLER" '[.nodes[].name] | .[]' "Docker Status"
assert_contains "command handler has Docker Restart"       "$CMD_HANDLER" '[.nodes[].name] | .[]' "Docker Restart"
assert_contains "command handler has Docker Stop"          "$CMD_HANDLER" '[.nodes[].name] | .[]' "Docker Stop"
assert_contains "command handler has Get Power Status"     "$CMD_HANDLER" '[.nodes[].name] | .[]' "Get Power Status"
assert_contains "command handler has Format Wake Status"   "$CMD_HANDLER" '[.nodes[].name] | .[]' "Format Wake Status"
assert_contains "command handler has System Access Denied" "$CMD_HANDLER" '[.nodes[].name] | .[]' "System Access Denied"
assert_contains "owner check uses TELEGRAM_OWNER_USERNAME" "$CMD_HANDLER" '[.nodes[] | select(.name=="System Owner Check")] | .[0].parameters.jsCode' "TELEGRAM_OWNER_USERNAME"
assert_contains "wake cmd uses pmset"                      "$CMD_HANDLER" '[.nodes[] | select(.name=="Get Power Status")] | .[0].parameters.command' "pmset"
assert_contains "restart cmd uses docker restart"          "$CMD_HANDLER" '[.nodes[] | select(.name=="Docker Restart")] | .[0].parameters.command' "docker restart ronkbot-n8n"
assert_contains "stop cmd uses docker stop"                "$CMD_HANDLER" '[.nodes[] | select(.name=="Docker Stop")] | .[0].parameters.command' "docker stop ronkbot-n8n"
assert_contains "help text includes /system"               "$CMD_HANDLER" '[.nodes[] | select(.name=="Help Response")] | .[0].parameters.text' "/system"

# ── docker-compose socket mount ────────────────────────────────────────────────
assert_file_contains "docker-compose mounts docker socket" "${REPO_ROOT}/docker-compose.yml" "/var/run/docker.sock"

# ── Scripts ────────────────────────────────────────────────────────────────────
assert_file_exists "create-shortcut.sh exists" "${SCRIPTS_DIR}/create-shortcut.sh"

# ── Docs ───────────────────────────────────────────────────────────────────────
assert_file_contains "COMMANDS.md has /system"             "${DOCS_DIR}/COMMANDS.md"  "/system"
assert_file_contains "README has remote control section"   "${REPO_ROOT}/README.md"   "Remote Control"

echo ""
echo "Results: ${PASS} passed, ${FAIL} failed"
if [ "${FAIL}" -gt 0 ]; then
  echo "Failed tests:"
  for e in "${ERRORS[@]}"; do echo "  - ${e}"; done
  exit 1
fi
echo "All system workflow structure tests passed."
