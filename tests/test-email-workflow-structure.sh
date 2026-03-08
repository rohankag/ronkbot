#!/usr/bin/env bash
# Test: Email workflow structural integrity
# Verifies that the command handler correctly wires email commands
# and that all email workflows have expected node types.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
WF_DIR="${REPO_ROOT}/n8n-workflows"

PASS=0
FAIL=0
ERRORS=()

assert_jq() {
  local label="$1"
  local file="$2"
  local query="$3"
  local expected="$4"

  local actual
  actual="$(jq -r "${query}" "${file}" 2>/dev/null || echo "__JQ_ERROR__")"

  if [ "${actual}" = "${expected}" ]; then
    echo "  PASS: ${label}"
    PASS=$((PASS + 1))
  else
    echo "  FAIL: ${label}"
    echo "        expected: ${expected}"
    echo "        actual:   ${actual}"
    ERRORS+=("${label}")
    FAIL=$((FAIL + 1))
  fi
}

assert_contains() {
  local label="$1"
  local file="$2"
  local query="$3"
  local needle="$4"

  local result
  result="$(jq -r "${query}" "${file}" 2>/dev/null || echo "__JQ_ERROR__")"

  if echo "${result}" | grep -qF "${needle}"; then
    echo "  PASS: ${label}"
    PASS=$((PASS + 1))
  else
    echo "  FAIL: ${label} (expected to find '${needle}')"
    ERRORS+=("${label}")
    FAIL=$((FAIL + 1))
  fi
}

assert_file_exists() {
  local label="$1"
  local file="$2"
  if [ -f "${file}" ]; then
    echo "  PASS: ${label}"
    PASS=$((PASS + 1))
  else
    echo "  FAIL: ${label} (file not found: ${file})"
    ERRORS+=("${label}")
    FAIL=$((FAIL + 1))
  fi
}

echo "==> Email Workflow Structure Tests"
echo ""

# ── 03-command-handler.json ────────────────────────────────────────────────────────
CH="${WF_DIR}/03-command-handler.json"
assert_file_exists "command handler file exists"                "${CH}"
assert_contains    "command handler has 'email' switch rule"   "${CH}" '.nodes[] | select(.name=="Route Command") | .parameters.rules.rules[].value' "email"
assert_contains    "command handler has Parse Email Subcommand" "${CH}" '[.nodes[].name]'  "Parse Email Subcommand"
assert_contains    "command handler has Route Email Subcommand" "${CH}" '[.nodes[].name]'  "Route Email Subcommand"
assert_contains    "command handler has Email Auth Message"     "${CH}" '[.nodes[].name]'  "Email Auth Message"
assert_contains    "command handler has Check Emails"           "${CH}" '[.nodes[].name]'  "Check Emails"
assert_contains    "command handler has Read Email"             "${CH}" '[.nodes[].name]'  "Read Email"
assert_contains    "command handler has Reply Email"            "${CH}" '[.nodes[].name]'  "Reply Email"
assert_contains    "command handler has Send Email"             "${CH}" '[.nodes[].name]'  "Send Email"
assert_contains    "command handler has Search Emails"          "${CH}" '[.nodes[].name]'  "Search Emails"
assert_contains    "help text includes /email"                  "${CH}" '.nodes[] | select(.name=="Help Response") | .parameters.text' "/email"

# ── 07-writing-style-analyzer.json ────────────────────────────────────────────────
SA="${WF_DIR}/07-writing-style-analyzer.json"
assert_file_exists "style analyzer file exists"                 "${SA}"
assert_contains    "style analyzer has Get Access Token"        "${SA}" '[.nodes[].name]' "Get Access Token"
assert_contains    "style analyzer has Fetch Sent Messages"     "${SA}" '[.nodes[].name]' "Fetch Sent Messages"
assert_contains    "style analyzer has Gemini Style Analysis"   "${SA}" '[.nodes[].name]' "Gemini Style Analysis"
assert_contains    "style analyzer has Save Writing Style"      "${SA}" '[.nodes[].name]' "Save Writing Style"
assert_contains    "style analyzer has Style Analysis Confirm"  "${SA}" '[.nodes[].name]' "Style Analysis Confirm"
assert_jq          "style analyzer name correct"                "${SA}" '.name' "07 - Writing Style Analyzer"

# ── 05-email-reader.json ───────────────────────────────────────────────────────────
ER="${WF_DIR}/05-email-reader.json"
assert_file_exists "email reader file exists"                   "${ER}"
assert_contains    "email reader has Get Access Token"          "${ER}" '[.nodes[].name]' "Get Access Token"
assert_contains    "email reader has Fetch Email List"          "${ER}" '[.nodes[].name]' "Fetch Email List"
assert_contains    "email reader has Parse Email Content"       "${ER}" '[.nodes[].name]' "Parse Email Content"
assert_contains    "email reader has Cache Email"               "${ER}" '[.nodes[].name]' "Cache Email"

# ── 06-email-sender.json ───────────────────────────────────────────────────────────
ES="${WF_DIR}/06-email-sender.json"
assert_file_exists "email sender file exists"                   "${ES}"

# ── Documentation files ─────────────────────────────────────────────────────────────
assert_file_exists "EMAIL_SETUP.md exists"   "${REPO_ROOT}/docs/EMAIL_SETUP.md"

# Doc content checks (grep, not jq — these are plain Markdown)
grep_contains() {
  local label="$1"
  local file="$2"
  local needle="$3"
  if grep -qF "${needle}" "${file}" 2>/dev/null; then
    echo "  PASS: ${label}"
    PASS=$((PASS + 1))
  else
    echo "  FAIL: ${label} (expected to find '${needle}' in ${file##*/})"
    ERRORS+=("${label}")
    FAIL=$((FAIL + 1))
  fi
}

grep_contains "README has email section" "${REPO_ROOT}/README.md"       "email"
grep_contains "COMMANDS.md has /email"   "${REPO_ROOT}/docs/COMMANDS.md" "/email"

echo ""
echo "Results: ${PASS} passed, ${FAIL} failed"

if [ "${FAIL}" -gt 0 ]; then
  echo ""
  echo "Failed assertions:"
  for e in "${ERRORS[@]}"; do
    echo "  - ${e}"
  done
  exit 1
fi

echo "All email workflow structure tests passed."
