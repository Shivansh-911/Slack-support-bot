#!/usr/bin/env bash
# Applies cma/agent.yaml, cma/environment.yaml, and every agent definition
# under cma/agents/<name>/agent.yaml.
#
# The cma/agents/ half mirrors upload_skills.sh's own pattern exactly: each
# agent lives in its own cma/agents/<name>/ folder (agent.yaml at its root,
# same shape as a skill's <name>/SKILL.md), and cma/agents/.manifest.json
# maps <name> -> agent_id, the same role cma/skills/.manifest.json plays for
# skill_ids. First run for a given agent: `ant beta:agents create`, id
# recorded in the manifest. Later runs for that name: version looked up via
# `ant beta:agents retrieve`, then `ant beta:agents update` against it — so
# editing agent.yaml and re-running updates in place instead of creating a
# duplicate agent.
#
# cma/agent.yaml (singular, legacy) and cma/environment.yaml are unrelated
# to that and untouched by this change — they're read by Django itself via
# CMA_AGENT_ID/CMA_ENVIRONMENT_ID in .env, so they stay env-var-based rather
# than manifest-based.
#
# This only talks to the Agents/Environments API — it does not create the
# Slack MCP server, upload skills, or touch Django. Run
# cma/scripts/upload_skills.sh first if any agent yaml's skills: list
# references a skill_id that doesn't exist yet.
#
# If an agent.yaml's `multiagent.agents` roster (or anything else in it)
# still carries an unresolved REPLACE_WITH_*_ID placeholder — e.g. before
# slack-search-agent/asana-search-agent have been synced and their real
# ids hand-substituted into orchestrator-agent's roster — that folder is
# skipped (with a warning) rather than sent to the API to fail there.
# Re-run `sync_agent.sh agents` (or `sync_agent.sh agents <name>`) after
# substituting.
#
# Usage: cma/scripts/sync_agent.sh [agent|agents [name ...]|environment]
#   No arg: syncs agent + environment (the legacy single-agent path) — does
#     NOT touch cma/agents/, so a plain run never auto-provisions the new
#     agents. agent: cma/agent.yaml only. agents: cma/agents/<name>/
#     folder(s), printing a name -> agent_id summary at the end — no names
#     given syncs every folder, one or more names syncs only those (e.g.
#     `sync_agent.sh agents orchestrator-agent`). environment:
#     cma/environment.yaml only.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"
AGENT_YAML="$REPO_ROOT/cma/agent.yaml"
AGENTS_DIR="$REPO_ROOT/cma/agents"
AGENTS_MANIFEST="$AGENTS_DIR/.manifest.json"
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

# Creates or updates one cma/agents/<name>/ folder, appending its name to
# the caller's synced_names/skipped_names arrays (bash locals are visible
# down the call stack, so sync_agents_folder's arrays are in scope here).
sync_one_agent_folder() {
  local name="$1" yaml_file="$2"

  if grep -q "REPLACE_WITH_" "$yaml_file"; then
    echo "skipping $name: unresolved REPLACE_WITH_* placeholder(s) — fill in the real agent id(s) first" >&2
    skipped_names+=("$name")
    return
  fi

  local existing_id
  existing_id="$(jq -r --arg k "$name" '.[$k].agent_id // empty' "$AGENTS_MANIFEST")"

  if [ -n "$existing_id" ]; then
    echo "Updating agent '$name' ($existing_id)..."
    local version
    version="$(ant beta:agents retrieve --agent-id "$existing_id" --transform version -r)"
    ant beta:agents update --agent-id "$existing_id" --version "$version" < "$yaml_file"
    echo "  -> updated $existing_id (was version $version)"
  else
    echo "Creating agent '$name'..."
    local agent_id
    agent_id="$(ant beta:agents create < "$yaml_file" --transform id -r)"
    local tmp
    tmp="$(mktemp)"
    jq --arg k "$name" --arg id "$agent_id" '.[$k] = {agent_id: $id}' "$AGENTS_MANIFEST" > "$tmp"
    mv "$tmp" "$AGENTS_MANIFEST"
    echo "  -> created $agent_id"
  fi
  synced_names+=("$name")
}

# Prints the trailing name -> agent_id summary from the caller's
# synced_names/skipped_names arrays.
print_agents_summary() {
  echo
  echo "Agents in $AGENTS_DIR:"
  local n
  # macOS ships bash 3.2, where "${arr[@]}" on a zero-length array throws
  # "unbound variable" under set -u even though the array was declared —
  # guard each loop on a nonzero count rather than expanding directly.
  if [ "${#synced_names[@]}" -gt 0 ]; then
    for n in "${synced_names[@]}"; do
      printf '  %-28s %s\n' "$n" "$(jq -r --arg k "$n" '.[$k].agent_id' "$AGENTS_MANIFEST")"
    done
  fi
  if [ "${#skipped_names[@]}" -gt 0 ]; then
    for n in "${skipped_names[@]}"; do
      printf '  %-28s %s\n' "$n" "(not synced — unresolved placeholder)"
    done
  fi
}

sync_agents_folder() {
  if [ ! -d "$AGENTS_DIR" ]; then
    echo "no $AGENTS_DIR, nothing to sync" >&2
    return
  fi
  if ! command -v jq >/dev/null 2>&1; then
    echo "error: 'jq' is required (used to read/write $AGENTS_MANIFEST)" >&2
    exit 1
  fi

  [ -f "$AGENTS_MANIFEST" ] || echo '{}' > "$AGENTS_MANIFEST"

  local synced_names=() skipped_names=()

  # With names given (e.g. `agents orchestrator-agent`), sync only those
  # folders instead of globbing every cma/agents/<name>/.
  local names=("$@")
  local dir name yaml_file
  if [ "${#names[@]}" -gt 0 ]; then
    for name in "${names[@]}"; do
      yaml_file="$AGENTS_DIR/$name/agent.yaml"

      if [ ! -f "$yaml_file" ]; then
        echo "skip $name: no agent.yaml at $yaml_file" >&2
        continue
      fi

      sync_one_agent_folder "$name" "$yaml_file"
    done
    print_agents_summary
    return
  fi

  shopt -s nullglob
  for dir in "$AGENTS_DIR"/*/; do
    name="$(basename "$dir")"
    yaml_file="$dir/agent.yaml"

    if [ ! -f "$yaml_file" ]; then
      echo "skip $name: no agent.yaml at $yaml_file" >&2
      continue
    fi

    sync_one_agent_folder "$name" "$yaml_file"
  done
  shopt -u nullglob

  print_agents_summary
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
  agents) shift; sync_agents_folder "$@" ;;
  environment) sync_environment ;;
  both) sync_agent; sync_environment ;;
  *)
    echo "usage: $0 [agent|agents [name ...]|environment]" >&2
    exit 1
    ;;
esac
