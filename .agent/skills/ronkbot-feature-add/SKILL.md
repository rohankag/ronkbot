---
name: ronkbot Feature Add
description: >
  Repeatable checklist for adding a new feature (command or integration) to ronkbot.
  Follow this every time you add workflows, commands, docs, and tests to keep the
  project consistent and well-documented.
---

# ronkbot Feature Add Skill

Use this skill whenever you are adding a new feature to **ronkbot** — whether that's
a new slash command, a new integration (Calendar, WhatsApp, etc.), or an extension
to an existing workflow.

---

## 1. Workflow Authoring Conventions

All n8n workflow files live in `n8n-workflows/` and follow a strict naming scheme:

```
XX-descriptive-name.json
```

Where `XX` is the next sequential two-digit number (check existing files first).

### Node naming rules

- Use **Title Case** with spaces: `"Parse Email Subcommand"`, `"Fetch Email List"`
- Trigger nodes are always named `"Execute Workflow Trigger"`
- Telegram send nodes follow pattern: `"[Action] [Target]"` e.g. `"Email Auth Message"`, `"Style Analysis Confirm"`

### Position grid

Use a left-to-right flow:

- Start x: `250`, increment by `200` per column
- y: `300` for the main flow; use `200`/`400`/`500` etc. for parallel branches

### Credential references

Never hardcode credentials. Always reference by ID:

```json
"credentials": {
  "telegramApi": { "id": "telegram-credentials", "name": "Telegram Bot (auto)" },
  "sqlite": { "id": "ronkbot-db", "name": "ronkbot Database" }
}
```

### Environment variables in expressions

Use `$env.VARIABLE_NAME`:

```
={{ $env.GEMINI_API_KEY }}
={{ $env.GEMINI_MODEL || 'gemini-2.0-flash' }}
```

---

## 2. Command Handler Wiring Checklist

When adding a new top-level command (e.g., `/calendar`, `/github`):

1. **Open** `n8n-workflows/03-command-handler.json`
2. **Find** the `"Route Command"` Switch node
3. **Add** a new rule entry in `.parameters.rules.rules`:

   ```json
   { "value": "yournewcommand", "output": <next_output_index> }
   ```

4. **Add** downstream nodes for the command
5. **Add** a connection in `.connections["Route Command"].main[<output_index>]`
6. **Update** the Help Response node `.parameters.text` to include `/yournewcommand`

If the command has **subcommands** (like `/email check`, `/email read`):

1. Add a `"Parse [Feature] Subcommand"` Code node immediately after the main route
2. Add a `"Route [Feature] Subcommand"` Switch node after that
3. Each subcommand output connects to either an `"Execute Workflow"` node (calls another workflow) or an inline Telegram message node

### Execute Workflow node template

```json
{
  "parameters": {
    "workflowId": "05 - Email Reader",
    "workflowInputs": {
      "values": [
        { "name": "chatId",   "stringValue": "={{ $json.chatId }}" },
        { "name": "userId",   "stringValue": "={{ $json.userId }}" },
        { "name": "username", "stringValue": "={{ $json.username }}" },
        { "name": "mode",     "stringValue": "check" }
      ]
    }
  },
  "name": "Check Emails",
  "type": "n8n-nodes-base.executeWorkflow",
  "typeVersion": 1.1,
  "position": [1300, 650]
}
```

---

## 3. Documentation Update Checklist

After every feature addition, update **all three** of these:

### README.md

- Add the feature to the **Features** bullet list (✨ Features section)
- Add commands to the **Available Commands** table
- Link to any new setup doc in `docs/`

### docs/COMMANDS.md

- Add a new `### /yourcommand` section with:
  - Usage examples
  - Expected response format (code block)
  - Notes on security/limitations

### docs/[FEATURE]_SETUP.md (new file if needed)

Create a setup guide for any feature that requires:

- External API credentials
- OAuth flows
- Non-trivial configuration

Template sections:

1. Prerequisites
2. Step-by-step setup
3. Available commands table
4. Troubleshooting
5. Privacy notes

---

## 4. Test Addition Checklist

Every feature must have tests. Add to `tests/`:

### Structural tests (always required)

Create or update `tests/test-[feature]-workflow-structure.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
WF_DIR="${REPO_ROOT}/n8n-workflows"

PASS=0; FAIL=0; ERRORS=()

assert_contains() {
  local label="$1" file="$2" query="$3" needle="$4"
  local result; result="$(jq -r "${query}" "${file}" 2>/dev/null || echo "__ERR__")"
  if echo "${result}" | grep -qF "${needle}"; then
    echo "  PASS: ${label}"; PASS=$((PASS+1))
  else
    echo "  FAIL: ${label}"; ERRORS+=("${label}"); FAIL=$((FAIL+1))
  fi
}

# Add your assertions here...

echo "Results: ${PASS} passed, ${FAIL} failed"
[ "${FAIL}" -eq 0 ] || exit 1
```

**What to assert:**

- New workflow file exists
- Command handler has the new switch case value
- All expected node names exist in the workflow
- Help text includes the new command
- Documentation files exist and contain the command string

### Register in run-tests.sh

Add one line to `tests/run-tests.sh`:

```bash
run_test "My Feature Structure"   "${SCRIPT_DIR}/test-myfeature-workflow-structure.sh"
```

---

## 5. PR / Commit Checklist

Before committing a new feature:

- [ ] Workflow JSON is valid (`bash tests/test-json-valid.sh`)
- [ ] ShellCheck passes on all new `.sh` files (`bash tests/test-shellcheck.sh`)
- [ ] Structural tests pass (`bash tests/test-myfeature-workflow-structure.sh`)
- [ ] Full suite passes (`bash tests/run-tests.sh --skip-docker`)
- [ ] `EMAIL_INTEGRATION_PROGRESS.md` or equivalent status doc updated
- [ ] `README.md` updated
- [ ] `docs/COMMANDS.md` updated
- [ ] Setup guide written (if feature needs credentials/OAuth)
- [ ] `config.example.env` updated with any new environment variables

---

## 6. Environment Variables Convention

When a feature needs new config, add to **`config.example.env`** with:

```bash
# [Feature Name] (Optional/Required)
FEATURE_ENABLED=false
FEATURE_CLIENT_ID=
FEATURE_CLIENT_SECRET=
# Description of what the variable does
FEATURE_SOME_OPTION=default_value
```

Always default to `false` for optional features so the bot still works without them.

---

## 7. Security Safeguards

### Never expose secrets

- **Never embed API keys** directly in workflow JSON. Use `$env.VAR_NAME` expressions.
- **Never log full messages** to external services when sensitive content is detected.
- **Never send sensitive data to cloud AI providers**. The Safety Check node in `02-gemini-chat.json` detects patterns like API keys, passwords, SSNs, and credit card numbers, and routes them to Ollama (local) only.

### Sensitive content detection patterns

The following patterns trigger local-only (Ollama) routing:

| Pattern | Example |
|---------|---------|
| API key prefixes | `ghp_`, `gsk_`, `sk-`, `AIzaSy`, `xoxb-`, `AKIA` |
| Password mentions | `password is ...`, `pwd = ...` |
| Credit card numbers | `4111 1111 1111 1111` |
| SSN format | `123-45-6789` |
| Store secret | `remember my token ...`, `save my key ...` |
| Private keys | `-----BEGIN RSA PRIVATE KEY-----` |

### Provider trust tiers

| Tier | Provider | When used |
|------|----------|-----------|
| 🟢 Trusted (local) | Ollama `llama3.3:70b` | Sensitive content, `/private` mode |
| 🟡 Cloud (general) | GitHub Models, Groq, Gemini | Normal chat (fallback order) |

### Audit logging

All AI calls are logged locally in Docker container logs with the `[AUDIT]` prefix:

```
[AUDIT] 2026-03-02T02:26:00Z | GitHub Models | "hey does this work..." | sensitive:false
[AUDIT] 2026-03-02T02:28:00Z | Ollama (local-private) | [SENSITIVE-REDACTED] | sensitive:true
```

### Access control

- The `01-telegram-listener.json` workflow checks `TELEGRAM_OWNER_USERNAME` from `.env`
- Non-owner messages get `⛔ This bot is private. Access denied.`
- Never remove the `Is Owner?` gate node

### Webhook configuration

- The listener uses a **Webhook node** (not TelegramTrigger) at path `/webhook/telegram-bot-webhook`
- After any Docker restart, the Telegram webhook must be re-set:

  ```bash
  curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook?url=$NGROK_URL/webhook/telegram-bot-webhook"
  ```

---

## Quick Reference: Key Files

| Purpose | File |
|---------|------|
| Main command router | `n8n-workflows/03-command-handler.json` |
| AI fallback + safety | `n8n-workflows/02-gemini-chat.json` |
| Telegram listener | `n8n-workflows/01-telegram-listener.json` |
| All tests | `tests/run-tests.sh` |
| JSON validation | `tests/test-json-valid.sh` |
| Config template | `config.example.env` |
| Command reference | `docs/COMMANDS.md` |
| Main readme | `README.md` |
