#!/bin/bash
set -euo pipefail

cd "$HOME/ai-trend-reporter-runtime"

# Ensure Homebrew tools are visible for launchd's minimal environment.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

# Hard guard against accidental API fallback in scheduled local operation.
export LLM_PROVIDER="ollama"
export LLM_FALLBACK_PROVIDER=""
export OLLAMA_MODEL="${OLLAMA_MODEL:-qwen2.5:14b}"
export OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://localhost:11434}"
export OLLAMA_NUM_CTX="${OLLAMA_NUM_CTX:-8192}"
export OLLAMA_TIMEOUT="${OLLAMA_TIMEOUT:-550}"
export LLM_BATCH_SIZE="${LLM_BATCH_SIZE:-5}"
# Existing GitHub Secrets have the currently valid Gmail app password. If the
# stale local SMTP password is rejected, dispatch an email-only workflow instead.
export EMAIL_FALLBACK_PROVIDER="${EMAIL_FALLBACK_PROVIDER:-github_actions}"
export GITHUB_EMAIL_REPO="${GITHUB_EMAIL_REPO:-ohkyuetaek/ai-trend-reporter}"
export GITHUB_EMAIL_WORKFLOW="${GITHUB_EMAIL_WORKFLOW:-send-email.yml}"

# Fail fast if Ollama is not reachable; launchd log will capture the error.
curl -fsS "$OLLAMA_BASE_URL/api/tags" >/dev/null

exec "$HOME/ai-trend-reporter-runtime/.venv/bin/python" main.py
