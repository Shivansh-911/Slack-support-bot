---
name: slack-channel-first-search
description: >-
  Primary Slack retrieval strategy: read channel history directly instead of
  searching, whenever a channel and/or a person can be resolved from the
  question. Scopes to the one channel named, or to every whitelisted channel
  in turn if none was named; when a person is named, gates each channel on
  their membership before reading it. Falls back to slack-search-2's
  search-based strategy only when a named person isn't a member of any
  channel in scope, or when direct reads across the whole scope turn up
  nothing relevant. Consult this skill first, before slack-search-2, for any
  Slack question that names or implies a channel or a person — it changes the
  default from "search first" to "read the channel first."
---

# Slack Channel-First Search

Most Slack questions name, or clearly imply, either a channel or a person.
When they do, reading that channel's actual history is more reliable than
searching it — search ranks and truncates, a direct read doesn't. This skill
is the default entry point for that shape of question. It hands off to
`slack-search-2` for its search-based strategy only once direct reading has
genuinely run out of road — see Step 3.

## When this applies

- The question names a channel (explicitly, or by nickname like "the deploy
  channel") → scope is that one channel.
- The question doesn't name a channel → scope is every whitelisted channel,
  run through Step 2 **independently, one at a time** — this is a sequence of
  direct reads, not a pooled search.
- Either way, if the question also names a person, resolve them and use their
  channel membership as a gate in Step 2.

This is the strategy to try **first**. Only drop into `search_whitelisted_channels`
(Step 3) once this procedure has been run to the end of its scope without an
answer.

## Step 1: Resolve what the question names

Use the same tools and the same resolution mechanics `slack-search-2` documents
in its own Step 1 — `channels_list` for a channel name, `users_search` falling
back to `search_users_directory` for a person, `usergroups_list` for a
group/handle. That skill covers the ambiguous-name and fuzzy-match nuance in
full; this skill only changes what happens *after* resolution, so don't
duplicate that reasoning here — read it there if a resolution gets ambiguous.

- **Channel resolved** → that ID is your scope for Step 2.
- **No channel named** → scope is every whitelisted channel; Step 2 runs
  against each one in turn.
- **Person resolved** → carry their user ID into Step 2 as the membership
  gate. If resolution comes back with nothing (not even a fuzzy match),
  treat the question as if no person was named — skip the membership gate
  entirely rather than blocking on it.

## Step 2: Per-channel procedure

Run this once for the single resolved channel, or once per whitelisted
channel in sequence if no channel was named.

1. **If a person was resolved**, check their membership in this specific
   channel with `list_channel_members` before reading anything — this is a
   gate, not just a disambiguation signal here:
   - **They're a member (or were recently — it's a point-in-time snapshot,
     so don't treat recent departure as disqualifying)** → continue to step 2.
   - **They're not a member of this channel** → don't pull this channel's
     history. If scope is "every whitelisted channel," move on to the next
     one. If this was the one named channel, there's nothing left to try
     here — go to Step 3.
   - **No person was resolved** (none was named) → skip this check, go
     straight to step 2 for every channel in scope.
2. **Pull the channel's full top-level history** with `conversations_history`.
   Don't default to `slack-search-2`'s short "read-directly" window; this
   read hasn't been narrowed by a search first, so under-reading here is how
   real content gets missed.
   - When the question implies a timeframe, use a duration string covering
     it (`"7d"`, `"30d"`, ...).
   - When it doesn't, **don't stop at the `"90d"` duration string** — that's
     the longest fixed duration this tool takes, not a real boundary on what
     Slack retains. Switch to a count-based `limit` (e.g. `"200"`) and page
     with `cursor` until `has_more` comes back `false`, so "full history"
     actually means the channel's full history, however far back that goes.
   - Keep `include_activity_messages: false` throughout.
3. **Analyze the top-level skeleton for relevance** — same reading discipline
   `slack-search-2` describes in "Read what you found": note who answered,
   where reply volume clusters, don't mistake a proposal for a decision.
4. **Expand into `conversations_replies`** for any top-level message that's
   on-topic or carries meaningful reply volume — same expand criteria as
   `slack-search-2`.
5. If scope is "every whitelisted channel," move to the next channel and
   repeat from step 1 of this procedure (re-check membership there — being a
   member of one whitelisted channel says nothing about another).

## Step 3: Fall back to search — only now

Switch to `search_whitelisted_channels` and follow `slack-search-2` in full —
its query-building, `term_clauses`, semantic-vs-keyword guidance, the
reformulation ladder, and the unscoped-search loop all apply as written there
— once either of these holds:

- **A named person isn't a member of any channel in scope.** Direct reads
  have nothing to check in that case, so there's nothing further Step 2 can
  do.
- **Step 2 ran to the end of its scope** (the one named channel, or every
  whitelisted channel) **and nothing relevant turned up.** A direct read
  coming up empty isn't the same as a search coming up empty — search can
  surface content outside the window you read, or reachable only through
  relevance ranking rather than a chronological scan — so this is a real
  fallback, not a formality to skip.

Once you're in this fallback, hand off to `slack-search-2` completely for
that search — don't blend the two strategies in one fallback call. Its
failure-handling buckets (self-caused / boundary / infrastructure) and
reading discipline apply here too, including during Step 2's direct reads: a
`list_channel_members` or `conversations_history` call that errors is not
evidence the person or the content isn't there, any more than a failed search
would be.

## Worked examples

The channels, people, and topics below are **placeholders** showing the shape
of each move — not real entities in this workspace. Never carry a name or ID
from these examples into an actual tool call.

**"Did Alex report anything about the deploy in #eng-support?"** — channel and
person both named.

1. `channels_list` → resolve `#eng-support`. `users_search` → resolve "Alex."
2. `list_channel_members` on `#eng-support` → Alex is a member.
3. `conversations_history` on `#eng-support`, wide window (no timeframe given,
   so lean toward the largest available).
4. Skeleton shows two on-topic threads mentioning the deploy.
5. `conversations_replies` on both.
6. Answer from what's there.

**"Has anyone mentioned the new pricing model?"** — no channel, no person.

1. Nothing to resolve; scope is every whitelisted channel.
2. No person, so no membership gate — go straight to `conversations_history`
   for channel A. Nothing relevant in the skeleton.
3. Repeat for channel B, then channel C. Nothing relevant in either.
4. Scope exhausted, nothing found — fall back to `search_whitelisted_channels`
   per `slack-search-2`, e.g. query `pricing model`.

**"Did Priya say anything in #finance?"** — person resolved, not a member of
the named channel.

1. `channels_list` → resolve `#finance`. `users_search` → resolve "Priya."
2. `list_channel_members` on `#finance` → Priya isn't listed.
3. Nothing left for Step 2 to do here — go straight to Step 3:
   `search_whitelisted_channels` scoped to `#finance`
   (`channel_ids: [<finance-id>]`), following `slack-search-2`'s
   query-building (e.g. `from:` her handle if resolved, or her name as plain
   text otherwise).

**"Did Sam mention the export bug anywhere?"** — no channel named, person
named, present in some whitelisted channels but not others.

1. `users_search` → resolve "Sam." No channel named → scope is every
   whitelisted channel.
2. Channel A: Sam is a member → `conversations_history` → skeleton has
   nothing relevant.
3. Channel B: Sam is not a member → skip straight to channel C, no history
   pull for B.
4. Channel C: Sam is a member → `conversations_history` surfaces an on-topic
   thread → `conversations_replies` on it → this is the answer.
5. No fallback needed — Step 2 found something relevant before exhausting
   its scope.
