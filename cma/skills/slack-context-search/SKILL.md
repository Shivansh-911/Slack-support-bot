---
name: slack-context-search
description: Search Slack via search_whitelisted_channels, the only Slack retrieval tool available. Use for any Slack question — channel activity, who said/decided what, team discussions, incidents, or "check Slack" requests.
---

# Slack Context Search

`search_whitelisted_channels` is the only Slack retrieval mechanism. There is
no fallback — no channel history, thread API, or other search tool.

The flow: resolve scope → build one strong query → search → evaluate → refine
only if needed → answer from evidence.

## 1. Resolve scope

**Channel** — If the user names one or more channels, restrict to those IDs.
Otherwise search all readable channels. Never guess an ID; only use IDs that
are already known to be allowlisted or that you've explicitly resolved. If a
supplied ID fails allowlist validation, the whole call is invalid — don't
retry it unchanged, substitute a guess, or silently widen the search to the
whole workspace.

**Person** — Resolve with `users_search`, taking the closest unambiguous
match. If nothing matches, drop the person constraint and continue.

**Team / usergroup** — References like "platform team," "@backend-team," or
"infra team" often map to a Slack usergroup. Call `usergroups_list` and match
on handle or name (exact match first, then closest unambiguous). A resolved
usergroup's members are a relevance/attribution signal, not an author or a
channel filter — don't gate search by membership, and don't attribute an
individual's message to the group. If no match, just treat the phrase as a
normal topic keyword.

## 2. Build the query

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

## 3. Apply filters

- **Time** — translate explicit ranges ("yesterday," "since Monday") into
  `after`/`before`. Never invent timestamps, and don't quietly widen the
  window just because a search came back thin.
<!-- - **Sort** — `score` for relevance questions; `timestamp` for "latest/recent";
  `timestamp` + `sort_dir: asc` when reconstructing a sequence of events. -->
- **Context** (`include_context_messages: true`) — turn on for why/how,
  decisions, incidents, disagreements, or any short/ambiguous message where
  surrounding conversation changes the meaning. Skip it for simple factual
  lookups.
- **Bots and deleted users** — default both off (`include_bots: false`,
  `include_deleted_users: false`). Only include them when the user asks or
  when historical attribution specifically requires it.

## 4. Evaluate and refine

After each search, classify the result:

| Evidence | Action |
|---|---|
| Direct answer | Stop. |
| Partial | One targeted refinement (change one dimension: wording, semantic↔keyword, term clause, time, channel). |
| Weak or none | Try a genuinely different angle once, then report that no relevant evidence was found — don't fabricate an answer or keep varying the same query. |

Preserve explicit channel, time, and person/team constraints through
refinement. A tool error is not evidence of absence — surface the failure,
don't report "nothing found" or retry the identical invalid call.

Paginate (`cursor`) only when the question needs broader or comprehensive
coverage and current results are insufficient — not just because a
`next_cursor` exists. `assistant.search.context` has tight rate limits, so
one well-built search beats several small ones.

## 5. Answer

- Attribute statements to their actual author; never expose raw Slack user
  IDs — resolve names with `get_user_profile` only when needed for the
  answer.
- Don't claim a channel, person, or usergroup doesn't exist unless the
  matching resolution step actually failed to find it.

Everything else about how the final answer is worded, scoped, or trimmed —
verb precision, handling conflicting evidence, confidence gating — is the
answering skill's job. Hand off the resolved evidence and let it decide.

## Examples

**"What did the platform team handle this month?"**
Resolve "platform team" → usergroups_list. Search all readable channels,
semantic query on platform work this month, use members for
relevance/attribution, add context if needed.

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