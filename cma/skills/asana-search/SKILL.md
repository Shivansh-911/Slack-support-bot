---
name: asana-search
description: Search Asana with the asana_* custom tools, always scoped to the whitelisted workspace/project. Use for anything Asana-related — "what's on my Asana list", "status of task X", "what's in project Y", an app.asana.com URL or gid — and also for any mention of a "ticket"/"support ticket"/"issue" or whether a Slack thread is "associated with"/"linked to"/"filed as" one, even when the same question also names a Slack channel. Read-only.
---

# Asana Search

These tools mirror roychri/mcp-server-asana's read-only tool set by name and purpose,
but run as custom tools executed by Django rather than an MCP server — that changes
nothing about how you use them, only how the whitelist is enforced (see Access boundary
below).

## Strategy

1. **Always include the whitelisted workspace/project gid** (given to you in the system prompt)
   on every tool call whose input accepts one — `workspace_gid`, `project_gid`, or an equivalent
   field. Never omit it and never substitute a different gid, even if the tool would technically
   run without one. A call outside it is rejected before it reaches Asana; retrying with a
   different gid won't work either.
2. **For "what's in the project" / "list everything" questions**, use `asana_get_tasks_for_project`.
   For anything else — including a keyword/filtered lookup that comes back empty — use
   `asana_search_tasks` instead of guessing at a task gid; see Search economy below for why
   `asana_get_tasks_for_project` is not the next step when a search finds nothing.
3. **For "what's on my list"**, use `asana_get_my_tasks`.
4. **A bare gid from the user (e.g. a pasted app.asana.com URL) still works directly** on
   `asana_get_task`, `asana_get_task_stories`, `asana_get_subtasks`, `asana_get_tags_for_task`,
   `asana_get_tag`, `asana_get_tasks_for_tag`, or `asana_get_multiple_tasks_by_gid` — each of these
   resolves the gid to its governing project/workspace and checks that against the whitelist
   itself before returning anything, so an out-of-scope gid comes back as a plain refusal rather
   than data. The one exception is `asana_get_project_status`: Asana's status-update record carries
   no project/workspace reference at all, so only call it on a status gid you already got from a
   whitelist-checked `asana_get_project_statuses` call — never a bare gid from anywhere else.
5. **For a task's comments/activity**, use `asana_get_task_stories`.
6. **For project structure** (sections, status, task counts), use `asana_get_project`,
   `asana_get_project_sections`, `asana_get_project_task_counts`, `asana_get_project_status`, or
   `asana_get_project_statuses`.

There's exactly one workspace and project in scope for the whole session (set in the
system prompt), so nothing here needs to search across or pick between projects/workspaces
— every tool below already assumes that single target.

## Search economy

`asana_search_tasks` ranks by loose term relevance inside the one whitelisted project,
which is a shared multi-client support backlog. A bare generic technical term ("404",
"GA4", "GSC", "AMP") searched on its own scans that whole backlog and comes back full of
other clients' unrelated tasks — that's expensive, not just imprecise, since every
irrelevant task's full fields land in context.

- **Always anchor a free-text query with the specific client/entity name** from the
  question, combined with the actual issue terms, in one query — e.g.
  `"Rising Kashmir 404 GA4 GSC"`, not three separate searches for `"Rising Kashmir"`,
  `"404 extended slug"`, and `"GA4 GSC"`. Never run a bare generic-term search with the
  client/entity name dropped from it.
- **One well-constructed query beats several narrow variations fired in parallel.** Build
  it from every term the question actually gives you before calling the tool, rather than
  searching term-by-term and widening later.
- **After a search, classify the result before deciding whether to search again:**

  | Result | Action |
  |---|---|
  | Relevant match(es) | Stop searching; report them. |
  | Only irrelevant matches (e.g. the client name matched other tasks, not this issue) | Report no relevant tasks found — don't start dropping the client name to chase more hits. |
  | Nothing at all | Try one genuinely different phrasing of the same client + issue, then stop and report no relevant tasks found. |

  Two searches total is the normal ceiling for one delegated question. Reaching for a
  third near-synonym variation almost never turns up what the first two missed — it just
  spends tokens re-scanning the same backlog.

`asana_get_tasks_for_project` is not part of this refinement loop. It returns the whitelisted
project's entire backlog — hundreds of tasks across every client it holds — so it's only for a
question that itself asks to list/browse everything, never a fallback reached for when
`asana_search_tasks` comes back empty or thin. A search finding nothing is a No relevant results
answer; escalating it to a full project listing costs far more than it recovers.

Once a search returns a candidate, resist pulling more detail than the question needs. A
task's name plus the fields `asana_search_tasks` already returned (assignee, completed,
due_on, permalink_url) are usually enough to judge relevance and to answer. Only call
`asana_get_task`/`asana_get_task_stories` on a candidate whose name already reads as a real
match — not on every loosely related hit — and never call either one twice on the same gid
in one conversation; reuse what the first call already returned.

## Tool guide

**`asana_get_tasks_for_project`** — every task in the whitelisted project, fully paginated.
Only for a question that explicitly asks for an exhaustive listing (see Search economy above)
— never a substitute for a keyword search, and never reached for after one comes back empty.

**`asana_search_tasks`** — free-text/filtered search, scoped by `workspace_gid`. This is Asana's
advanced search, which is **premium-only** and does not offset-paginate — results are capped at 100
and unstable-ordered. Always restricted to the whitelisted project(s) regardless of what's asked
for. The default tool for anything keyword/filtered — see Search economy above for how to query
it without scanning the whole backlog.

**`asana_get_my_tasks`** — the caller's own tasks, scoped by `workspace_gid`.

**`asana_get_task`** — one task's full detail, by gid. Call only on a confirmed candidate (see
Search economy above), and only once per gid per conversation.

**`asana_get_task_stories`** — a task's comments and system activity. Same restraint as
`asana_get_task`: only on a confirmed candidate, only once per gid.

**`asana_get_subtasks`** — a task's subtasks.

**`asana_get_multiple_tasks_by_gid`** — batch lookup of up to 25 gids. Each is checked
individually; any not in scope come back listed under `skipped_not_whitelisted` instead of data.

**`asana_get_project`** / **`asana_get_project_sections`** / **`asana_get_project_task_counts`** —
project detail, its sections, and its task counts, scoped by `project_gid`.

**`asana_get_project_status`** / **`asana_get_project_statuses`** — a project's status updates.
`asana_get_project_statuses` is scoped by `project_gid`; `asana_get_project_status` takes a single
status gid and carries no project field — only call it on a status gid returned by
`asana_get_project_statuses` (see Strategy #4).

**`asana_get_tag`** / **`asana_get_tags_for_task`** / **`asana_get_tasks_for_tag`** /
**`asana_get_tags_for_workspace`** — tag lookups. `asana_get_tags_for_workspace` is scoped by
`workspace_gid` directly; the others take a bare `tag_gid`/`task_gid`, resolved to their governing
workspace/project internally.

No write tools exist here at all — not disabled-but-present, simply not implemented. If asked to
create, update, complete, comment on, or otherwise modify anything in Asana, say plainly that you
can only read it.

## Access boundary

Every one of these tools checks constants.py's `WHITELISTED_ASANA_WORKSPACES` /
`WHITELISTED_ASANA_PROJECTS` itself, in code, before calling Asana — via `AsanaGateService` for
tools that carry a workspace/project gid directly, and `AsanaScopeService` for tools that only
carry a tag/section/task gid (resolving to the governing workspace/project first). A refusal is a
boundary, not an error — don't retry it, don't reach for another tool to route around it, and tell
the user plainly that it's out of scope. The one gap is `asana_get_project_status` (see Strategy
#4 and Tool guide above) — there is no code-level check for it, only the gid-provenance rule.

Hand off the raw evidence (task data, comments, `permalink_url`s) to the answering skill —
it decides what surfaces and in what format; this skill's job stops at retrieval.