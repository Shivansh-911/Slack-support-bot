#!/usr/bin/env bash
# Pushes every file in cma/memory/ to a same-named memory in the
# slack-whitelisted-channels memory store (CMA_WHITELISTED_CHANNELS in
# .env) — the read-only allowlist mounted into every session by
# AgentSessionCreateService._resources.
#
# This is a manual, developer-run push, not a runtime sync: nothing in
# Django or the agent calls this script. Edit files under cma/memory/,
# then run this, whenever the whitelist actually changes.
#
# Each file cma/memory/<name> is pushed to memory path /<name> — add a new
# file to the directory and it is picked up automatically, no script edit
# needed.
#
# No separate id is cached anywhere for this: every run lists
# CMA_WHITELISTED_CHANNELS's contents once to check which memory paths
# already exist there, and only creates the ones that don't.
#
# Usage: cma/scripts/sync_whitelisted_channels.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"
MEMORY_DIR="$REPO_ROOT/cma/memory"

if ! command -v ant >/dev/null 2>&1; then
  echo "error: 'ant' CLI not found on PATH" >&2
  exit 1
fi
if ! command -v jq >/dev/null 2>&1; then
  echo "error: 'jq' not found on PATH" >&2
  exit 1
fi

[ -f "$ENV_FILE" ] || touch "$ENV_FILE"
[ -d "$MEMORY_DIR" ] || { echo "error: $MEMORY_DIR not found" >&2; exit 1; }

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

files=("$MEMORY_DIR"/*)
if [ ! -e "${files[0]}" ]; then
  echo "error: $MEMORY_DIR is empty — nothing to sync" >&2
  exit 1
fi

# `list` streams one JSON object per memory (not a wrapped array), so jq's
# default per-input filtering finds each path without -s. Listed once and
# reused for every file below instead of round-tripping per file.
existing="$(ant beta:memory-stores:memories list --memory-store-id "$store_id" --path-prefix /)"

for file in "${files[@]}"; do
  [ -f "$file" ] || continue

  name="$(basename "$file")"
  memory_path="/$name"
  content="$(cat "$file")"

  memory_id="$(
    echo "$existing" \
      | jq -r "select(.path == \"$memory_path\") | .id" \
      | head -n1
  )"

  if [ -z "$memory_id" ]; then
    echo "$memory_path not found in $store_id — creating it..."
    memory_id="$(ant beta:memory-stores:memories create \
      --memory-store-id "$store_id" \
      --path "$memory_path" \
      --content "$content" \
      --transform id -r)"
    echo "  -> created $memory_id"
  else
    echo "Updating $memory_path ($memory_id) in $store_id from $file..."
    ant beta:memory-stores:memories update \
      --memory-store-id "$store_id" \
      --memory-id "$memory_id" \
      --content "$content" \
      >/dev/null
    echo "  -> updated $memory_id"
  fi
done
