---
name: asana-search-2
description: Search Asana with the asana_* custom tools, always scoped to the whitelisted workspace. Use for anything Asana-related — "what's on my Asana list", "status of task X", "what's in project Y", an app.asana.com URL or gid — and also for any mention of a "ticket"/"support ticket"/"issue" or whether a Slack thread is "associated with"/"linked to"/"filed as" one. Read-only.
---

# Asana Search

Read-only tools mirroring roychri/mcp-server-asana. Every tool checks the
whitelist server-side — out-of-scope calls come back empty/refused, not
filtered client-side. So you never need to resolve a project gid up front
just to stay in scope.

## Strategy

1. **Search first.** For anything naming a client/entity/issue, go straight
   to `asana_search_tasks`. Combine client name + issue terms in one query
   (e.g. `"Rising Kashmir 404 GA4 GSC"`), not separate searches per term.
2. **Two searches max.** If the first returns nothing, try one genuinely
   different angle (different issue term, date, or assignee) — then stop.
3. **Disambiguate from results, not before.** Keep `projects.name` in
   `opt_fields`. If relevant hits span conflicting projects, ask the user
   which one — using the candidates you already have.
4. **Full project listing/summary** → `asana_get_tasks_for_project`, but
   only when explicitly asked to list/summarize a whole (already-identified)
   project. Never use it to search a backlog locally after a thin search —
   that's a "no relevant results" answer instead.
5. **"What's on my list"** → `asana_get_my_tasks` (workspace-wide).
6. **A pasted gid/URL** → use directly on `asana_get_task`,
   `asana_get_task_stories`, `asana_get_subtasks`, or
   `asana_get_multiple_tasks_by_gid`; each self-checks the whitelist.

**Result → action:**

| Result | Action |
|---|---|
| Relevant match(es), one project | Report them. |
| Relevant match(es), conflicting projects | Ask user to disambiguate. |
| Only irrelevant matches | Report none found — don't drop the client name. |
| Nothing | One different angle, then report none found. |

Only call `asana_get_task`/`asana_get_task_stories` on a name-confirmed
candidate, and never twice on the same gid.

## Tool guide

- **`asana_search_tasks`** — free-text search, workspace-scoped. Set
  `opt_fields` to `name,gid,assignee.name,completed,due_on,permalink_url,projects.name`
  unless more is needed. Capped at 100 unstable-ordered results, no
  pagination — use `asana_get_tasks_for_project` for exhaustive listing.
  Use `projects_any` only to narrow a retry or confirm a known project —
  not as a default.
- **`asana_get_tasks_for_project`** — full listing of one already-identified
  project, only when that's explicitly what's asked for.
- **`asana_get_my_tasks`** — caller's own tasks, workspace-scoped.
- **`asana_get_task`** — one task's full detail, once per gid.
- **`asana_get_task_stories`** — comments/activity, only when asked about
  updates/history.
- **`asana_get_subtasks`** — a task's subtasks.
- **`asana_get_multiple_tasks_by_gid`** — batch lookup, up to 25 gids;
  out-of-scope ones return under `skipped_not_whitelisted`.
- **`asana_get_project`** — one project's detail, once you have its gid.

No write tools exist — if asked to create/update/complete/comment, say you
can only read.

## Access boundary

Every tool checks the whitelist server-side before calling Asana. A refusal
is a boundary — don't retry it or route around it with another tool.

Hand off raw evidence (task data, comments, `permalink_url`s) to the
answering skill — this skill's job stops at retrieval.