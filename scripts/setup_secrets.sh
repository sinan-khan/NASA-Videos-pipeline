#!/usr/bin/env bash
# One-shot helper: push all required values into GitHub repository Secrets.
#
# Usage:
#   gh auth login
#   bash scripts/setup_secrets.sh your-gh-user/your-repo
#
# Set env vars before running, or let the script prompt you.
set -euo pipefail

REPO="${1:?Usage: $0 owner/repo}"

echo "This script is interactive. Add the following secrets to ${REPO}:"
echo ""

prompt() {
  local name="$1" current="${2:-}"
  if [ -n "${current}" ]; then
    echo "  - ${name} (already set)"
    return
  fi
  read -rsp "  ${name}: " val
  echo
  gh secret set "${name}" --repo "${REPO}" --body "${val}"
}

prompt GROQ_API_KEY "${GROQ_API_KEY:-}"
prompt NASA_API_KEY "${NASA_API_KEY:-}"
prompt YT_CLIENT_ID "${YT_CLIENT_ID:-}"
prompt YT_CLIENT_SECRET "${YT_CLIENT_SECRET:-}"
prompt YT_REFRESH_TOKEN "${YT_REFRESH_TOKEN:-}"
prompt YT_PRIVACY_STATUS "${YT_PRIVACY_STATUS:-private}"
prompt YT_LANGUAGE "${YT_LANGUAGE:-en}"

echo ""
echo "Optional secrets (skip with Enter, defaults are sane):"
read -rp "  CHANNEL_HANDLE (your @handle, shown as watermark) [blank to skip]: " handle
[ -n "${handle}" ] && gh secret set CHANNEL_HANDLE --repo "${REPO}" --body "${handle}"
read -rp "  NOTIFY_WEBHOOK (Discord/Slack URL for failure alerts) [blank to skip]: " webhook
[ -n "${webhook}" ] && gh secret set NOTIFY_WEBHOOK --repo "${REPO}" --body "${webhook}"

echo ""
echo "Done. Verify with: gh secret list --repo ${REPO}"
