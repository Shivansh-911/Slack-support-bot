#!/usr/bin/env bash
# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0
# list asana tasks end-to-end with curl + jq: GET /tasks filtered by project, tag, section, or
# assignee+workspace, send an opt_fields list, follow next_page.offset through every page, surface
# the {errors:[...]} envelope, and emit tsv or jsonl. generic to any asana workspace — everything
# instance-specific comes from env vars or flags.

set -euo pipefail

usage() {
  cat <<'EOF'
usage:
  asana_tasks.sh --project GID [options]
  asana_tasks.sh --tag GID [options]
  asana_tasks.sh --section GID [options]
  asana_tasks.sh --assignee GID|me --workspace GID [options]

  exactly one selector is required: --project, --tag, --section, or --assignee (with --workspace).

options:
  --project GID           list tasks in a project
  --tag GID               list tasks carrying a tag
  --section GID           list tasks in a section
  --assignee GID|me       list a user's tasks; requires --workspace ("me" resolves the caller)
  --workspace GID         workspace for --assignee
  --completed-since WHEN  only tasks completed at/after WHEN (ISO 8601; "now" = incomplete only)
  --fields LIST           comma-separated opt_fields. default:
                          name,completed,assignee.name,due_on,permalink_url
  --limit N               stop after N tasks total (default 100; 0 = fetch everything)
  --page-size N           tasks per request page, 1..100 (default 100)
  --json                  emit one json object per task (jsonl) instead of tsv
  -h, --help              show this help

environment:
  ASANA_TOKEN     bearer token; injected by the runtime, so the placeholder default is fine
  ASANA_BASE      api root override (default https://app.asana.com/api/1.0); ASANA_BASE_URL also works

output:
  tasks on stdout — tsv with header (gid, name, completed, assignee, due_on, permalink_url) by
  default, jsonl with --json. the tsv columns are fixed; custom --fields selections show in --json.
  fetched count and any truncation warning go to stderr.

exit codes:
  0 success    1 request failed, api error, or bad arguments
EOF
}

err() { printf '%s\n' "$*" >&2; }

command -v curl >/dev/null || { err "curl is required"; exit 1; }
command -v jq >/dev/null || { err "jq is required"; exit 1; }

BASE_URL="${ASANA_BASE_URL:-${ASANA_BASE:-https://app.asana.com/api/1.0}}"
TOKEN="${ASANA_TOKEN:-placeholder}"
PROJECT=""
TAG=""
SECTION=""
ASSIGNEE=""
WORKSPACE=""
COMPLETED_SINCE=""
FIELDS="name,completed,assignee.name,due_on,permalink_url"
LIMIT=100
PAGE_SIZE=100
FORMAT=tsv

# require_int FLAG VALUE — flags that take a count must get a non-negative integer
require_int() {
  case "$2" in
    ''|*[!0-9]*) err "$1 needs a non-negative integer, got '${2:-nothing}'"; exit 1 ;;
  esac
}

while [ $# -gt 0 ]; do
  case "$1" in
    --project)
      [ -n "${2:-}" ] || { err "--project needs a gid"; exit 1; }
      PROJECT="$2"; shift 2 ;;
    --tag)
      [ -n "${2:-}" ] || { err "--tag needs a gid"; exit 1; }
      TAG="$2"; shift 2 ;;
    --section)
      [ -n "${2:-}" ] || { err "--section needs a gid"; exit 1; }
      SECTION="$2"; shift 2 ;;
    --assignee)
      [ -n "${2:-}" ] || { err "--assignee needs a gid or 'me'"; exit 1; }
      ASSIGNEE="$2"; shift 2 ;;
    --workspace)
      [ -n "${2:-}" ] || { err "--workspace needs a gid"; exit 1; }
      WORKSPACE="$2"; shift 2 ;;
    --completed-since)
      [ -n "${2:-}" ] || { err "--completed-since needs a value"; exit 1; }
      COMPLETED_SINCE="$2"; shift 2 ;;
    --fields)
      [ -n "${2:-}" ] || { err "--fields needs a comma-separated list"; exit 1; }
      FIELDS="$2"; shift 2 ;;
    --limit) require_int --limit "${2:-}"; LIMIT="$2"; shift 2 ;;
    --page-size)
      require_int --page-size "${2:-}"
      if [ "$2" -lt 1 ] || [ "$2" -gt 100 ]; then err "--page-size must be 1..100"; exit 1; fi
      PAGE_SIZE="$2"; shift 2 ;;
    --json) FORMAT=json; shift ;;
    -h|--help) usage; exit 0 ;;
    -*) err "unknown option: $1 (see --help)"; exit 1 ;;
    *) err "unexpected argument: $1 (see --help)"; exit 1 ;;
  esac
done

# exactly one selector among project / tag / section / assignee
SELECTORS=0
if [ -n "$PROJECT" ]; then SELECTORS=$(( SELECTORS + 1 )); fi
if [ -n "$TAG" ]; then SELECTORS=$(( SELECTORS + 1 )); fi
if [ -n "$SECTION" ]; then SELECTORS=$(( SELECTORS + 1 )); fi
if [ -n "$ASSIGNEE" ]; then SELECTORS=$(( SELECTORS + 1 )); fi
if [ "$SELECTORS" -eq 0 ]; then
  err "one selector required: --project, --tag, --section, or --assignee (see --help)"; exit 1
fi
if [ "$SELECTORS" -gt 1 ]; then
  err "use only one of --project / --tag / --section / --assignee"; exit 1
fi
if [ -n "$ASSIGNEE" ] && [ -z "$WORKSPACE" ]; then
  err "--assignee requires --workspace"; exit 1
fi

BASE_URL="${BASE_URL%/}"

asana_api() {
  curl -sS --max-time 60 \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "Accept: application/json" "$@"
}

# exit with the api's own message if the response is an error envelope (or not json at all)
asana_check_error() {
  if ! jq -e . >/dev/null 2>&1 <<<"$1"; then
    err "non-json response from the api:"
    printf '%s\n' "$1" | head -c 2000 >&2
    exit 1
  fi
  if [ "$(jq -r 'type == "object" and has("errors")' <<<"$1")" = "true" ]; then
    jq -r '"asana error: " +
      ([.errors[]?.message] | if length > 0 then join("; ") else "unknown error" end)' <<<"$1" >&2
    exit 1
  fi
}

# resolve --assignee me to the caller's gid (the assignee param wants a user id)
if [ "$ASSIGNEE" = "me" ]; then
  MERESP="$(asana_api "${BASE_URL}/users/me")"
  asana_check_error "$MERESP"
  ASSIGNEE="$(jq -r '.data.gid // empty' <<<"$MERESP")"
  [ -n "$ASSIGNEE" ] || { err "could not resolve 'me' to a user gid"; exit 1; }
fi

# static query params (offset is added per page in the loop). -G makes every --data-urlencode a
# query-string field on the GET, which also keeps values safely encoded.
QARGS=(-G)
if [ -n "$PROJECT" ]; then QARGS+=(--data-urlencode "project=${PROJECT}"); fi
if [ -n "$TAG" ]; then QARGS+=(--data-urlencode "tag=${TAG}"); fi
if [ -n "$SECTION" ]; then QARGS+=(--data-urlencode "section=${SECTION}"); fi
if [ -n "$ASSIGNEE" ]; then
  QARGS+=(--data-urlencode "assignee=${ASSIGNEE}" --data-urlencode "workspace=${WORKSPACE}")
fi
if [ -n "$COMPLETED_SINCE" ]; then
  QARGS+=(--data-urlencode "completed_since=${COMPLETED_SINCE}")
fi
QARGS+=(--data-urlencode "opt_fields=${FIELDS}" --data-urlencode "limit=${PAGE_SIZE}")

URL="${BASE_URL}/tasks"

# tsv cell rule: null -> "", nested -> json, else string (so completed=false stays "false")
read -r -d '' CELL <<'JQ' || true
def cell: if . == null then "" elif type=="object" or type=="array" then tojson else tostring end;
JQ

print_page() {
  if [ "$FORMAT" = "tsv" ]; then
    jq -r --argjson take "$2" "$CELL"'
      .data[:$take][]
      | [ (.gid|cell), (.name|cell), (.completed|cell),
          (.assignee.name|cell), (.due_on|cell), (.permalink_url|cell) ]
      | @tsv' <<<"$1"
  else
    jq -c --argjson take "$2" '.data[:$take][]' <<<"$1"
  fi
}

OFFSET=""
FETCHED=0
HEADER_DONE=0

while :; do
  if [ -n "$OFFSET" ]; then
    PAGE="$(asana_api "$URL" "${QARGS[@]}" --data-urlencode "offset=${OFFSET}")"
  else
    PAGE="$(asana_api "$URL" "${QARGS[@]}")"
  fi
  asana_check_error "$PAGE"

  if [ "$FORMAT" = "tsv" ] && [ "$HEADER_DONE" -eq 0 ]; then
    printf 'gid\tname\tcompleted\tassignee\tdue_on\tpermalink_url\n'
    HEADER_DONE=1
  fi

  COUNT="$(jq -r '.data | length' <<<"$PAGE")"
  TAKE="$COUNT"
  if [ "$LIMIT" -gt 0 ]; then
    REMAINING=$(( LIMIT - FETCHED ))
    if [ "$COUNT" -gt "$REMAINING" ]; then TAKE="$REMAINING"; fi
  fi
  if [ "$TAKE" -gt 0 ]; then print_page "$PAGE" "$TAKE"; fi
  FETCHED=$(( FETCHED + TAKE ))

  OFFSET="$(jq -r '.next_page.offset // empty' <<<"$PAGE")"

  if [ "$LIMIT" -gt 0 ] && [ "$FETCHED" -ge "$LIMIT" ]; then
    if [ -n "$OFFSET" ] || [ "$COUNT" -gt "$TAKE" ]; then
      err "output truncated at ${FETCHED} task(s) (raise --limit, or 0 for everything)"
    fi
    break
  fi
  if [ -z "$OFFSET" ]; then break; fi
done

err "fetched ${FETCHED} task(s)"