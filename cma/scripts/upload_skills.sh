#!/usr/bin/env bash
# Pushes every cma/skills/<name>/ folder to the Skills API.
#
# First run for a given skill: `ant beta:skills create`, records the
# returned skill_id in cma/skills/.manifest.json.
# Later runs for the same skill: `ant beta:skills:versions create` against
# that recorded skill_id, so editing a skill's files and re-running this
# pushes a new version instead of creating a duplicate skill.
#
# Does not touch cma/agent.yaml — after this prints a skill_id + version,
# put it into agent.yaml's `skills:` list yourself and run sync_agent.sh.
#
# Usage: cma/scripts/upload_skills.sh [skill-name ...]
#   No args: uploads every skill folder under cma/skills/.
#   One or more names: uploads only those.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_DIR="$SCRIPT_DIR/../skills"
MANIFEST="$SKILLS_DIR/.manifest.json"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

if ! command -v ant >/dev/null 2>&1; then
  echo "error: 'ant' CLI not found on PATH" >&2
  exit 1
fi

if ! command -v zip >/dev/null 2>&1; then
  echo "error: 'zip' is required (skills upload as a single zip archive)" >&2
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "error: 'jq' is required (used to read/write $MANIFEST)" >&2
  exit 1
fi

[ -f "$MANIFEST" ] || echo '{}' > "$MANIFEST"

if [ "$#" -gt 0 ]; then
  names=("$@")
else
  names=()
  for dir in "$SKILLS_DIR"/*/; do
    [ -d "$dir" ] || continue
    names+=("$(basename "$dir")")
  done
fi

if [ "${#names[@]}" -eq 0 ]; then
  echo "No skill folders found under $SKILLS_DIR" >&2
  exit 1
fi

for name in "${names[@]}"; do
  dir="$SKILLS_DIR/$name"

  if [ ! -f "$dir/SKILL.md" ]; then
    echo "skip $name: no SKILL.md at $dir/SKILL.md" >&2
    continue
  fi

  # Zipped upload, per the Skills API docs — the zip's internal top-level
  # entry is the skill's own directory name (SKILL.md at $name/SKILL.md
  # inside the archive), which is what "SKILL.md must be exactly in the
  # top-level folder" actually means: one named folder deep, not bare at the
  # archive root and not nested any deeper. Building the zip from $SKILLS_DIR
  # (not $dir) is what gives it that $name/ prefix.
  zip_path="$TMP_DIR/$name.zip"
  (cd "$SKILLS_DIR" && zip -rq "$zip_path" "$name" -x '*.DS_Store')

  existing_id="$(jq -r --arg k "$name" '.[$k].skill_id // empty' "$MANIFEST")"

  if [ -n "$existing_id" ]; then
    echo "Updating skill '$name' ($existing_id)..."
    version="$(ant beta:skills:versions create \
      --skill-id "$existing_id" \
      --file "$zip_path" \
      --transform version -r)"
    echo "  -> skill_id: $existing_id, version: $version"
  else
    echo "Creating skill '$name'..."
    skill_id="$(ant beta:skills create \
      --display-title "$name" \
      --file "$zip_path" \
      --transform id -r)"
    tmp="$(mktemp)"
    jq --arg k "$name" --arg id "$skill_id" '.[$k] = {skill_id: $id}' "$MANIFEST" > "$tmp"
    mv "$tmp" "$MANIFEST"
    echo "  -> skill_id: $skill_id, version: 1"
  fi
done

echo
echo "Put the printed skill_id (+ version, if you want to pin rather than"
echo "use 'latest') into cma/agent.yaml's skills: list, then run"
echo "cma/scripts/sync_agent.sh."
