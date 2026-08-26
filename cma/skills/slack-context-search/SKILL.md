---
name: slack-context-search
description: Search Slack via search_whitelisted_channels, the only Slack retrieval tool available. Use for any Slack question — channel activity, who said/decided what, team discussions, incidents, or "check Slack" requests.
---

# Slack Context Search

`search_whitelisted_channels` is the only Slack retrieval mechanism. There is
no fallback — no channel history, thread API, or other search tool.

The flow: check memory → resolve scope → build one strong query → search →
evaluate → refine only if needed → answer from evidence.

## 1. Check memory first

Resolving a channel, person, or usergroup by name is a repeated cost across
turns and conversations — before calling any resolution tool in step 2,
check memory for that exact fact first.

| Fact | Memory first | Tool if missing/stale |
|---|---|---|
| Channel directory (name → channel_id) | Check memory | `list_channels` |
| A specific person's profile | Check memory | `users_search` then `get_user_profile` |
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
Otherwise search all readable channels. Never guess an ID; only use IDs that
are already known to be allowlisted or that you've explicitly resolved
(memory first, then `list_channels` per step 1). A supplied ID that fails
allowlist validation is dropped from the call, not fatal to it — the search
still runs with whichever IDs remain, and the reply notes which were
dropped. Only if *every* supplied ID fails validation does the call return
an error instead of running; don't retry that case unchanged, substitute a
guess, or silently widen the search to the whole workspace.
`context_channel_id` is a single ID, not a list — if it fails allowlist
validation the call is rejected outright, same as any other single-channel
field.

**Person** — Check memory for this person first (step 1). If absent,
resolve with `users_search`, taking the closest unambiguous match, and cache
the resolved profile to memory. If nothing matches, drop the person
constraint and continue.

**Team / usergroup** — References like "platform team," "@backend-team," or
"infra team" often map to a Slack usergroup. Check memory for the usergroup
directory first (step 1). If absent, call `list_usergroups` and match on
handle or name (exact match first, then closest unambiguous), then cache the
directory to memory. A resolved usergroup's members are a relevance/
attribution signal, not an author or a channel filter — don't gate search by
membership, and don't attribute an individual's message to the group. If no
match, just treat the phrase as a normal topic keyword.

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
- **`with:<@user_id>`** filters to messages involving that person.

## 4. Apply filters

- **Time** — translate explicit ranges ("yesterday," "since Monday") into
  `after`/`before`. Never invent timestamps, and don't quietly widen the
  window just because a search came back thin.
<!-- - **Sort** — `score` for relevance questions; `timestamp` for "latest/recent";
  `timestamp` + `sort_dir: asc` when reconstructing a sequence of events. -->
- **Context** — leave `include_context_messages` off (the default) on
  `search_whitelisted_channels` itself; don't request it up front. It's
  billed per result across the whole result set, not just the hit that
  needs it. Instead, evaluate the plain search result first (step 5), and
  only when a *specific* matched message's meaning genuinely depends on
  surrounding conversation — why/how, a decision, an incident,
  a disagreement, or a short/ambiguous message on its own — fetch that
  one thread directly with `conversations_replies` (the message's
  channel + its thread_ts, from the permalink or the result's own fields).
  That scopes the extra cost to the one or two hits that actually need it
  instead of paying for context on every result. If that message turns
  out not to be part of a thread, `conversations_replies` just returns it
  alone — that's a cheap confirmation, not an error.
- **Bots and deleted users** — default both off (`include_bots: false`,
  `include_deleted_users: false`). Only include them when the user asks or
  when historical attribution specifically requires it.

## 5. Evaluate and refine

Search one call at a time by default: issue a single `search_whitelisted_channels`
call, wait for its result, and evaluate before deciding whether another call
is needed. Don't fire several searches in parallel and reconcile the results
afterward — most questions resolve in one call, and evaluating before the
next one is what lets you stop there instead of over-searching. The
exception is when the question itself asks for something that genuinely
needs multiple independent angles at once (e.g. "compare how #a and #b each
handled X," or an explicit request for a deep/comprehensive sweep) — there,
parallel calls across the distinct angles are appropriate.

After each search, read the result and judge how much of the question it
actually answers before doing anything else. This is a judgment call, not
literal counting — but as a rule of thumb, once you're roughly 60% or more
of the way to a complete answer, that's enough: stop and answer from what
you have rather than searching further to round it out. Going deeper past
that point is only for when the question itself explicitly asks for a deep
or comprehensive sweep.

| Evidence | Action |
|---|---|
| Direct answer, or roughly 60%+ of it covered | Stop. Answer from what you have; note the small gap, if any, rather than closing it with another search. |
| Meaningful gap (roughly under 60% covered) | One targeted refinement (change one dimension: wording, semantic↔keyword, term clause, time, channel). |
| Weak or none | Try a genuinely different angle once, then report that no relevant evidence was found — don't fabricate an answer or keep varying the same query. |

Preserve explicit channel, time, and person/team constraints through
refinement. A tool error is not evidence of absence — surface the failure,
don't report "nothing found" or retry the identical invalid call.

Paginate (`cursor`) only when the question needs broader or comprehensive
coverage and current results are insufficient — not just because a
`next_cursor` exists. `assistant.search.context` has tight rate limits, so
one well-built search beats several small ones.

## 6. Answer

- Attribute statements to their actual author; never expose raw Slack user
  IDs — resolve names per the agent's memory-first rule, whatever point in
  the turn you're resolving them at.
- Don't claim a channel, person, or usergroup doesn't exist unless the
  matching resolution step actually failed to find it.

Everything else about how the final answer is worded, scoped, or trimmed —
verb precision, handling conflicting evidence, confidence gating — is the
answering skill's job. Hand off the resolved evidence and let it decide.

## Examples

**"What did the platform team handle this month?"**
Resolve "platform team" → check memory for the usergroup directory first,
`list_usergroups` if absent. Search all readable channels, semantic query on
platform work this month, use members for relevance/attribution, add
context if needed.

**"What did Alex say about the deployment issue?"**
Resolve Alex. Semantic query: "Alex deployment issue." No channel restriction
unless one was named.

**"What happened in #deploy?"**
Resolve `#deploy`, restrict to it, skip person/team resolution unless the
question needs it, sort by recency, pull context if the events aren't
self-explanatory from single messages.

**"Has anyone discussed the new pricing model?"**
No channel/person constraint. Semantic query across all readable channels;
narrow with distinctive terminology only if results are too broad.