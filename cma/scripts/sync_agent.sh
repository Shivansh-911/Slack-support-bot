#!/usr/bin/env bash
# Applies cma/agent.yaml and cma/environment.yaml: creates each resource if
# its ID env var is unset, otherwise updates it in place (looking up the
# current version itself, rather than a hardcoded N, for the agent's
# optimistic-concurrency `--version` check).
#
# Reads/writes CMA_AGENT_ID and CMA_ENVIRONMENT_ID in .env (repo root) so a
# create only ever happens once; every later run is an update.
#
# This only talks to the Agents/Environments API — it does not create the
# Slack MCP server, upload skills, or touch Django. Run
# cma/scripts/upload_skills.sh first if agent.yaml's skills: list references
# a skill_id that doesn't exist yet.
#
# Usage: cma/scripts/sync_agent.sh [agent|environment]
#   No arg: syncs both. One arg: syncs only that resource.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"
AGENT_YAML="$REPO_ROOT/cma/agent.yaml"
ENVIRONMENT_YAML="$REPO_ROOT/cma/environment.yaml"

if ! command -v ant >/dev/null 2>&1; then
  echo "error: 'ant' CLI not found on PATH" >&2
  exit 1
fi

[ -f "$ENV_FILE" ] || touch "$ENV_FILE"

# Reads a KEY=value out of .env without exporting the whole file (it may
# hold secrets this script has no other reason to load into its own env).
read_env() {
  local key="$1"
  grep -m1 "^${key}=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true
}

# Upserts KEY=value in .env, appending if the key isn't present yet.
write_env() {
  local key="$1" value="$2"
  if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
    local tmp
    tmp="$(mktemp)"
    sed "s|^${key}=.*|${key}=${value}|" "$ENV_FILE" > "$tmp"
    mv "$tmp" "$ENV_FILE"
  else
    echo "${key}=${value}" >> "$ENV_FILE"
  fi
}

sync_agent() {
  local agent_id
  agent_id="$(read_env CMA_AGENT_ID)"

  if [ -z "$agent_id" ]; then
    echo "Creating agent from $AGENT_YAML..."
    agent_id="$(ant beta:agents create < "$AGENT_YAML" --transform id -r)"
    write_env CMA_AGENT_ID "$agent_id"
    echo "  -> created $agent_id, saved to .env"
  else
    echo "Updating agent $agent_id from $AGENT_YAML..."
    local version
    version="$(ant beta:agents retrieve --agent-id "$agent_id" --transform version -r)"
    ant beta:agents update --agent-id "$agent_id" --version "$version" < "$AGENT_YAML"
    echo "  -> updated $agent_id (was version $version)"
  fi
}

sync_environment() {
  local env_id
  env_id="$(read_env CMA_ENVIRONMENT_ID)"

  if [ -z "$env_id" ]; then
    echo "Creating environment from $ENVIRONMENT_YAML..."
    env_id="$(ant beta:environments create < "$ENVIRONMENT_YAML" --transform id -r)"
    write_env CMA_ENVIRONMENT_ID "$env_id"
    echo "  -> created $env_id, saved to .env"
  else
    echo "Updating environment $env_id from $ENVIRONMENT_YAML..."
    ant beta:environments update --environment-id "$env_id" < "$ENVIRONMENT_YAML"
    echo "  -> updated $env_id"
  fi
}

case "${1:-both}" in
  agent) sync_agent ;;
  environment) sync_environment ;;
  both) sync_agent; sync_environment ;;
  *)
    echo "usage: $0 [agent|environment]" >&2
    exit 1
    ;;
esac
