---
name: slack-search-3
description: Search Slack via search_whitelisted_channels, the only Slack retrieval tool available. Use for any Slack question — channel activity, who said/decided what, team discussions, incidents, or "check Slack" requests.
---

# Slack Context Search Procedure

The flow: check memory → resolve scope → build one strong query → search →
evaluate → refine only if needed → answer from evidence.

## 1. Check memory first

See the agent's memory-first resolution rule for the general policy. In
practice for this procedure, resolve against memory before touching any of
these tools:

| Fact | Memory first | Tool if missing/stale |
|---|---|---|
| Channel directory (name → channel_id) | Check memory | `list_channels` |
| A specific person's profile | Check memory | `get_user_profile` |
| Usergroup directory (handle/name → id + members) | Check memory | `list_usergroups` |

If memory already has the fact, use it directly and skip the tool call. If
memory is missing it, or it looks stale, call the tool — then write the
resolved fact back to memory so the next resolution, this conversation or a
later one, doesn't repeat the same call.

This gate covers name/ID resolution only. It never substitutes for
`search_whitelisted_channels` itself — message content always comes from a
live search, never from memory.

Check memory case-insensitively — a case-sensitive miss is not evidence the
fact is missing.

## 2. Resolve scope

**Channel** — If the user names one or more channels, restrict to those IDs.
Never guess an ID; only use IDs that are already known to be allowlisted or
that you've explicitly resolved (memory first, then `list_channels`). A
supplied ID that fails allowlist validation is dropped from the call, and
the reply notes which were dropped. Only if *every* supplied ID fails
validation does the call return an error instead of running; don't retry
that case unchanged, and don't silently widen the search to the whole
workspace.

**Person** — Check memory for this person first (step 1). If absent and you
already have their user_id (e.g. from context passed in, or from an earlier
result this turn), call `get_user_profile` to get their name — this tool
only accepts a user_id, never a name. If you only have a name and no ID:
there is no name-search tool available, so do not call `get_user_profile`
or `list_conversation_members` speculatively hoping to find them. Instead,
put the name directly into the search `query` text and let full-text search
surface their messages; resolve their user_id from the returned message
metadata as it appears, then cache the name→ID mapping to memory for next
time. Reserve `list_conversation_members` (expensive) for when the question
specifically requires enumerating everyone in a channel — never use it as a
way to look up one person's ID.

**Team / usergroup** — References like "platform team," "@backend-team," or
"infra team" often map to a Slack usergroup. Also watch for IDs shaped like
`S**********`, starting with `S`. Always check memory for the usergroup
directory first (step 1). If absent, call `list_usergroups` and match on
handle or name (exact match first, then closest unambiguous), then cache
the directory to memory.

## 3. Build the query

Construct the query from what's actually being asked, not the raw question.
Weight: topic > person > team > project/system > action/event.

- **Semantic search** (default) — for natural-language questions. Use a
  short, concept-dense query, e.g. "platform team migration discussion," not
  the full sentence.
- **Keyword search** (`disable_semantic_search: true`) — for exact strings
  that need literal matching: error messages, ticket IDs, feature/release
  names, API names, identifiers.
- **term_clauses** — add only when a specific term must appear verbatim and
  meaningfully sharpens precision. Don't repeat terms already in the query.
- **users_from** — use once a person's user_id is already known (from
  memory or a resolution earlier this turn) and the question should be
  restricted to messages they *authored*, not just messages that mention
  them. Don't use it while a name is still unresolved — resolve the person
  first (step 2), or fold their name into the query text instead if
  resolution isn't worth the cost for this question.

## 4. Apply filters

- **Time** — If a freshness cutoff or explicit range was given (e.g. "since
  Monday," "this month," "only after the orchestrator's memory cutoff"),
  convert it to a concrete Unix timestamp and pass it as `after` (and
  `before` if the range has an end). Resolve relative phrases against the
  current date/time available to you — never leave a stated time constraint
  unconverted, and never silently widen past a freshness cutoff you were
  given. If no time constraint is stated or implied by the question, leave
  `before`/`after` unset rather than guessing a default window.
- **Context** — leave `include_context_messages` off (the default) on
  `search_whitelisted_channels` itself; don't request it up front. It's
  billed per result across the whole result set, not just the hit that
  needs it. Instead, evaluate the plain search result first (step 5), and
  only when a *specific* matched message's meaning genuinely depends on
  surrounding conversation — why/how, a decision, an incident, a
  disagreement, or a short/ambiguous message on its own — fetch that one
  thread directly with `conversations_replies` (the message's channel + its
  thread_ts, from the permalink or the result's own fields). That scopes
  the extra cost to the one or two hits that actually need it instead of
  paying for context on every result. If that message turns out not to be
  part of a thread, `conversations_replies` just returns it alone — that's
  a cheap confirmation, not an error.
- **Bots and deleted users** — default both off (`include_bots: false`,
  `include_deleted_users: false`). Only include them when the user asks or
  when historical attribution specifically requires it.

## 5. Evaluate and refine

See the agent's research-quality rule for the underlying stop/continue
policy. In practice, use this table:

| Evidence | Action |
|---|---|
| Direct answer, or roughly 60%+ of it covered | Stop. Answer from what you have; note the small gap, if any, rather than closing it with another search. |
| Meaningful gap (roughly under 60% covered) | One targeted refinement (change one dimension: wording, semantic↔keyword, term clause, time, channel). |
| Weak or none | Try a genuinely different angle once, then report that no relevant evidence was found — don't fabricate an answer or keep varying the same query. |

Search one call at a time by default: issue a single
`search_whitelisted_channels` call, wait for its result, and evaluate before
deciding whether another call is needed. Don't fire several searches in
parallel and reconcile the results afterward — most questions resolve in
one call, and evaluating before the next one is what lets you stop there
instead of over-searching. The exception is when the question itself asks
for something that genuinely needs multiple independent angles at once
(e.g. "compare how #a and #b each handled X," or an explicit request for a
deep/comprehensive sweep) — there, parallel calls across the distinct
angles are appropriate.

Preserve explicit channel, time, and person/team constraints through
refinement. A tool error is not evidence of absence — surface the failure,
don't report "nothing found" or retry the identical invalid call.

Paginate (`cursor`) only when the question needs broader or comprehensive
coverage and current results are insufficient — not just because a
`next_cursor` exists. `search_whitelisted_channels` has tight rate limits,
so one well-built search beats several small ones.

## 6. Answer

- Attribute statements to their actual author, using both their resolved
  real name and their user_id together, per the agent's output contract —
  resolve names via the memory-first rule before including them, but do not
  omit the user_id.
- Don't claim a channel, person, or usergroup doesn't exist unless the
  matching resolution step actually failed to find it.

Everything else about how the final answer is worded, scoped, or trimmed —
verb precision, handling conflicting evidence, confidence gating — is the
answering skill's job. Hand off the resolved evidence and let it decide.

## Examples

**"What did the platform team handle this month?"**
Resolve "platform team" → check memory for the usergroup directory first,
`list_usergroups` if absent. Convert "this month" to an `after` timestamp
for the 1st of the current month. Search all readable channels, semantic
query on platform work this month, use members for relevance/attribution,
add context if needed.

**"What did Alex say about the deployment issue?"**
Check memory for Alex. If not found, don't call `get_user_profile` or
`list_conversation_members` speculatively — search directly with a semantic
query: "Alex deployment issue." Resolve Alex's user_id from the result and
cache it. No channel restriction unless one was named.

**"What happened in #deploy?"**
Resolve `#deploy`, restrict to it, skip person/team resolution unless the
question needs it, sort by recency, pull context if the events aren't
self-explanatory from single messages.

**"Has anyone discussed the new pricing model?"**
No channel/person constraint. Semantic query across all readable channels;
narrow with distinctive terminology only if results are too broad.

**"What's changed in #incidents since last Tuesday?"**
Resolve `#incidents`, restrict to it. Convert "since last Tuesday" to an
`after` timestamp for that date. Semantic query on incident activity,
scoped by the time filter — don't widen past it even if results look thin.