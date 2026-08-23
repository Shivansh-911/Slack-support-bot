#!/usr/bin/env bash
# Pushes cma/memory/channel.md's content to the /channels.md memory in the
# slack-whitelisted-channels memory store (CMA_WHITELISTED_CHANNELS in
# .env) — the read-only allowlist mounted into every session by
# AgentSessionCreateService._resources.
#
# This is a manual, developer-run push, not a runtime sync: nothing in
# Django or the agent calls this script. Edit cma/memory/channel.md, then
# run this, whenever the whitelist actually changes.
#
# No separate id is cached anywhere for this: every run lists
# CMA_WHITELISTED_CHANNELS's contents to check whether /channels.md
# already exists there, and only creates it the first time.
#
# Usage: cma/scripts/sync_whitelisted_channels.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"
CHANNEL_MD="$REPO_ROOT/cma/memory/channel.md"
MEMORY_PATH="/channels.md"

if ! command -v ant >/dev/null 2>&1; then
  echo "error: 'ant' CLI not found on PATH" >&2
  exit 1
fi
if ! command -v jq >/dev/null 2>&1; then
  echo "error: 'jq' not found on PATH" >&2
  exit 1
fi

[ -f "$ENV_FILE" ] || touch "$ENV_FILE"
[ -f "$CHANNEL_MD" ] || { echo "error: $CHANNEL_MD not found" >&2; exit 1; }

# Reads a KEY=value out of .env without exporting the whole file (it may
# hold secrets this script has no other reason to load into its own env).
read_env() {
  local key="$1"
  grep -m1 "^${key}=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true
}

store_id="$(read_env CMA_WHITELISTED_CHANNELS)"
if [ -z "$store_id" ]; then
  echo "error: CMA_WHITELISTED_CHANNELS is not set in .env — create the store first" >&2
  exit 1
fi

content="$(cat "$CHANNEL_MD")"

# `list` streams one JSON object per memory (not a wrapped array), so jq's
# default per-input filtering finds the one at MEMORY_PATH without -s.
memory_id="$(
  ant beta:memory-stores:memories list --memory-store-id "$store_id" --path-prefix / \
    | jq -r "select(.path == \"$MEMORY_PATH\") | .id" \
    | head -n1
)"

if [ -z "$memory_id" ]; then
  echo "$MEMORY_PATH not found in $store_id — creating it..."
  memory_id="$(ant beta:memory-stores:memories create \
    --memory-store-id "$store_id" \
    --path "$MEMORY_PATH" \
    --content "$content" \
    --transform id -r)"
  echo "  -> created $memory_id"
else
  echo "Updating $MEMORY_PATH ($memory_id) in $store_id from $CHANNEL_MD..."
  ant beta:memory-stores:memories update \
    --memory-store-id "$store_id" \
    --memory-id "$memory_id" \
    --content "$content" \
    >/dev/null
  echo "  -> updated $memory_id"
fi
