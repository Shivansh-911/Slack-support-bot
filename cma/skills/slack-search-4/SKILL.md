---
name: slack-search-4
description: Search Slack via search_whitelisted_channels, the only Slack retrieval tool available. Use for any Slack question — channel activity, who said/decided what, team discussions, incidents, or "check Slack" requests.
---

# Slack Context Search Procedure

Flow: check memory → resolve scope → build a narrow, topic-anchored query → search → judge relevance → go deeper only while still relevant → answer.

## 1. Check memory first

| Fact | Memory first | Tool if missing/stale |
|---|---|---|
| Channel directory | Check memory | `list_channels` |
| Person's profile | Check memory | `get_user_profile` |
| Usergroup directory | Check memory | `list_usergroups` |

Cache newly resolved facts back to memory. Case-insensitive check. This never substitutes for a live search of message content.

## 2. Resolve scope

**Channel** — only use IDs already known allowlisted or resolved (memory → `list_channels`). Never guess. Non-allowlisted supplied IDs are dropped, not retried; only an all-invalid list errors out.

**Person** — memory first. If you have a user_id, `get_user_profile`. If you only have a name and it's not in memory, there's no name-search tool — put the name directly in the search `query` instead, resolve their ID from the results, then cache it. Only use `list_conversation_members` (expensive) to enumerate a whole channel, never to look up one person.

**Team/usergroup** — memory first, then `list_usergroups`, matching on handle/name.

## 3. Build a narrow query

Anchor on the specific topic named in the question — never on the project, channel, or team alone. A project name is rarely a sufficient query by itself if the question names something narrower within it; searching on the project alone surfaces unrelated activity and dilutes the answer.

- Lead with the topic's exact name/acronym as the query, optionally `disable_semantic_search: true`, or as a required `term_clauses` entry rather than a loosely weighted word.
- Use semantic search only if the exact-term pass is too narrow or you need paraphrased mentions — keep the topic term required via `term_clauses` even then.
- `users_from` — only once a person's ID is already resolved and the question needs messages they authored, not just mentioned them.
- **Person/usergroup as the subject** — if the question is about/to/involving a specific person or Slack user group (not just who wrote something), resolve them to their `user_id`/`usergroup_id` first (step 2), then run the first call's `query` as exactly `<@user_id>` or `<@usergroup_id>` — the mention token alone, nothing else in `query`. Other parameters (channel_ids, before/after, term_clauses, etc.) can still be set on that call. This surfaces messages that mention/tag them, which `users_from` (authored-by) doesn't catch. Refine with topic terms in later calls as needed.

## 4. Apply filters

- **Time** — convert any stated or implied cutoff/range into `after`/`before` (or `oldest`/`latest`) as plain date/date-time strings, e.g. `after: "2026-08-01"`, `before: "2026-08-31"` for "the month of August," reasoned against `current_datetime`. Never compute a raw Unix epoch number yourself — the backend converts the string deterministically; that's the whole point of passing text instead of doing the arithmetic. Never leave a stated time constraint unconverted; never widen past a given cutoff; leave unset if nothing was stated.
- **Context** — leave `include_context_messages` off; fetch `conversations_replies` only for the one message whose meaning genuinely depends on surrounding conversation.
- **Bots/deleted users** — off by default; include only if asked or attribution requires it.

## 5. Judge relevance, go deeper only while it holds

After each call, judge every result against the topic asked — not the project, channel, or person alone.

| Result | Action |
|---|---|
| On-topic, more likely exists | Go one step deeper (refine or paginate) in the same direction. |
| On-topic, no further leads | Stop. Answer from what you have. |
| Mixed on/off-topic | Keep only the on-topic results. |
| Off-topic or empty | Try one different angle; if that also fails, stop and report no relevant evidence — don't broaden scope to find something. |

If the question itself asks for something broad or comprehensive, breadth is the actual ask — don't narrow it to one sub-topic. Otherwise, stop the instant a step stops surfacing on-topic material; don't search further just because more results might exist. Preserve explicit constraints (channel/time/person) through refinement. A tool error is not evidence of absence.

**Hard ceiling: max 6 `search_whitelisted_channels` calls per question, no exceptions** — refinements and pagination count against it, and this applies even to a comprehensive/"everything" ask. Track your call count. At 6, stop and answer from what you have rather than issuing a 7th call; note any gap instead of searching further. This ceiling doesn't apply to `conversations_replies`, `conversations_history`, or the resolution tools (`list_channels`, `get_user_profile`, `list_usergroups`).

## 6. Answer

Attribute using both real name and user_id together. Only name someone as involved if an included, on-topic fact ties them to it — not because they were active in the same channel or project. Don't claim something doesn't exist unless resolution actually failed to find it.

If the question is about approval, consensus, sentiment, or who reacted to something, a message's `reactions` (returned by `conversations_replies` — emoji `name`, `count`, reacting `users`) is the evidence to cite, the same as a text fact. Skip reactions entirely for questions that aren't asking about them.