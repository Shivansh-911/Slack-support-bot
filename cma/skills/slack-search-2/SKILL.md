---
name: slack-search-2
description: >-
  Mechanics of finding and reading things in Slack: which tool to reach for, how
  to build and refine search queries, when to read a channel or thread directly,
  how to read results without over-claiming, and how to classify and recover
  from tool failures. Always use this skill whenever answering a question requires
  looking at Slack. Also use it when the user names a channel, pastes a Slack link, or
  asks something answerable only from workspace history. If the answer plausibly
  lives in Slack, consult this skill before calling any Slack tool.
---

# Searching Slack

Your Slack tools split into two jobs that are easy to confuse. Keeping them
straight is most of what makes retrieval work.


| Job                                          | Tool                                             | Reach                          | Shape of result                                         |
| -------------------------------------------- | ------------------------------------------------ | ------------------------------ | ------------------------------------------------------- |
| **Locate** — find *where* something was said | `search_whitelisted_channels`                    | Every readable channel at once | Ranked hits, max 20/page, optional surrounding messages |
| **Read** — see *what* was said around it     | `conversations_history`, `conversations_replies` | One channel or one thread      | Chronological messages, paged                           |


Locate is broad and shallow. Read is narrow and deep. Nearly every good answer is
**locate, then read**: search to find the two or three places that matter, then
read those places properly. Going straight to `conversations_history` on a hunch
burns budget scanning messages that don't matter; searching without then reading
gives you fragments you'll misinterpret.

There is no tool that fetches a single message by timestamp. You reach a specific
message by reading its channel or its thread.

**Search unscoped by default.** Omitting `channel_ids` searches everything you can
read, which is almost always what you want — you rarely know in advance which
channel holds the answer. Pass `channel_ids` — a list, even for a single channel —
only when the user explicitly restricted the question to one or more specific
channels. Passing several pools the results across all of them in one ranked set,
which is what you want when a topic spans channels; it's also the fix when a
single unscoped search comes back dominated by one noisy channel and you know
which channels the user actually cares about.

---



## Step 1: Resolve identifiers before anything else

Users refer to channels by nickname ("the deploy channel") and to people by first
name. Slack needs an ID and a real handle. Resolve first:

- **Channel name → ID**: `channels_list`. Required before any `channel_id` or
`channel_ids` argument. `conversations_history` also accepts `#name`, but
resolving first tells you whether the channel is reachable at all before you
spend a call finding out the hard way.
- **Person → user ID/handle**: `users_search`, before any `from:` modifier.
`from:` needs `@handle` or a user ID — a bare name won't match there even
though `users_search` itself will. `users_search` requires a non-empty
`query` (an empty one hard-errors, there's no "list everyone" mode) and
matches by exact substring against name/real name/display name/email, capped
at 100 results with no further paging. If it comes back empty, don't retry it
with the same query — go to `search_users_directory` instead (see below).
- **Group @handle → members**: `usergroups_list`, when the question is about a
team rather than a person.

Skip resolution only when the user gave you an ID or an exact `#handle` directly.

### When `users_search` comes back empty

This is a different failure than a channel search miss, and it's common
enough to have its own tool: `users_search` only matches a name that's a
literal (case-insensitive) substring of someone's username, real name,
display name, or email. A misspelling, or a short form that isn't literally
contained in any of those fields, returns nothing even though a human would
recognize it instantly.

**Don't reformulate** `users_search` **and don't give up after one empty result.**
Go straight to `search_users_directory` — it re-checks the same fields by
exact substring first, then falls back to fuzzy/typo-tolerant matching only
when that's also empty. Two things to carry forward from its result:

- **Match type matters.** Results are tagged `exact` or `fuzzy`. An `exact`
hit is as trustworthy as a `users_search` hit would have been. A `fuzzy` one
is a best guess — a misspelling or near-miss, not a confirmed identity. If
it matters who exactly this is (assigning something to them, saying they
said something), confirm the fuzzy match with the user rather than treating
it as settled.
- **A nickname unrelated to the real name won't resolve either way.** "Bob"
for "Robert" isn't a substring and isn't a typo of it — neither tool carries
a nickname dictionary. If both come back empty or only fuzzy, ask the user
for the person's actual Slack name or handle rather than guessing further.

**If the name matches more than one person**, pass `channel_id` (a channel
the user actually named, not one you're guessing at) to `search_users_directory`
— it flags which of the matches is currently a member of that channel, as a
disambiguation signal, not a filter. Someone who left the channel still shows
up, just marked as not currently in it, so don't discard a match on that basis
alone if the question is about something they said in the past.

**"Who's in this channel" is now answerable** via `list_channel_members` —
pass a resolved channel ID or name and get back real names, not bare IDs. It's
a point-in-time snapshot, so someone absent from it may still have posted
relevant history there before leaving.

**Every** `channel_id` **you use — alone or inside a** `channel_ids` **list — must
trace back to** `channels_list` **or to a search result.** Never construct one,
never lift one out of message text or a pasted permalink without resolving it
first, never adapt one by editing digits. An invented ID is the most common
cause of a denied call, and it produces a misleading "out of scope" signal for
something that may well be in scope. This matters more with a list: one bad ID
among several good ones fails the *entire* `search_whitelisted_channels` call,
not just that one channel — see the Boundary failures section below.

---



## Step 2: Pick the entry point from the question's shape


| The question looks like                             | Start with                                                                                             | Why                                                                                                  |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------- |
| "Has anyone mentioned X?" / "did we discuss Y?"     | `search_whitelisted_channels`, unscoped                                                                | Unknown location — that's what search is for                                                         |
| "What's our policy on X, and where does it say so?" | `search_whitelisted_channels`, unscoped                                                                | Needs the source, not just the fact                                                                  |
| "Catch me up on a named channel since Monday"       | `conversations_history` with a time-bounded `limit`                                                    | Location known, want everything in a window                                                          |
| "What got decided in this thread?"                  | `conversations_replies`                                                                                | One thread, read it whole                                                                            |
| "What's the latest on X?"                           | Search sorted by `timestamp`, then read                                                                | Recency matters more than relevance                                                                  |
| "Who owns X?" / "who should I ask about Y?"         | Search, then `users_search` on whoever answered                                                        | Ownership shows in who answers, not in titles                                                        |
| "What have I missed?"                               | `conversations_unreads`                                                                                | Purpose-built for exactly this                                                                       |
| User pasted a Slack link                            | Extract the channel ID and `thread_ts` from the URL, resolve the channel, then `conversations_replies` | Never search for something you've been handed — but do verify the link points somewhere you can read |


When the shape is genuinely ambiguous, search first. Search is cheaper than
scanning and it tells you where to read.

---



## Step 3: Build the query

Search matches what people actually typed. That has consequences.

**Use content words, not meta words.** The user's phrasing describes the *act of
asking*; the query needs words that appeared in the *original discussion*.

- "What did we decide about the caching rewrite last month?" → query
`caching rewrite`, with `after` set to a month ago. Not `decide discussion last month`.
- "Did anyone report the login bug?" → `login bug`, or better, the literal error
string if the user gave you one.

**Keep it to two to five distinctive terms.** Long queries over-constrain and
return nothing; single generic words return noise. Proper nouns, error codes,
ticket keys, service names, and feature names are the high-value tokens.

**Never put a pasted passage in the query.** If the user pastes a log, document,
or long message and asks whether it's come up before, pull three or four
identifying keywords out of it and search on those.

### Modifiers

Slack's search modifiers work inside `query` and are the most efficient way to
narrow — a modifier is free, a second search round-trip is not.

- `from:@handle` — one author. Resolve the handle first.
- `before:` / `after:` with dates, or the top-level `before` / `after` Unix
timestamp parameters. Prefer the top-level parameters; they're unambiguous.
- `has:link`, `has:file` — narrowing to messages carrying an artifact is often
how you find the doc someone shared.

**Do not use** `in:`**.** It's reserved for channel scoping and is applied
automatically from `channel_ids`.

### Term clauses — hard keyword requirements

`query` gets trimmed to two to five terms (above) so it stays loose enough
for semantic matching to bridge vocabulary gaps. That looseness is a
liability the moment the request carries something that must literally be
present in a real hit — a service name, an error code, a ticket key, a
specific identifier. Use `term_clauses` for those instead of cramming them
into `query` and hoping.

`term_clauses` is a hard filter, matched in conjunctive normal form: every
clause must match (AND across clauses), and any one term inside a clause
satisfies it (OR within a clause).

```
term_clauses: [["gizmo-service"], ["ECONNRESET", "connection reset"]]
```

means: mentions `gizmo-service`, **and** (`ECONNRESET` **or** "connection
reset").

- **One clause per required concept, not per word.** Don't split "connection
  reset" into two single-term clauses — that turns an AND-of-ORs into an
  over-constrained AND-of-ANDs and starts returning nothing.
- **Group synonyms or alternate spellings inside a clause** when you have
  more than one wording for the same concept (an error's log form and its
  prose form, a service's old name and new name) — that's what the inner OR
  is for.
- **`query` and `term_clauses` aren't competing for the same term budget.**
  Once the hard requirements live in `term_clauses`, `query` is free to stay
  a fuller, closer-to-the-original-question phrase rather than a trimmed
  keyword list — semantic ranking gets more to work with, while
  `term_clauses` guarantees the essential terms survive regardless of how
  that ranking goes.
- The `modifiers` param (top-level `modifier:value` pairs, distinct from a
  modifier typed inline in `query`) filters against `term_clauses`
  specifically, per Slack's docs — it doesn't touch the semantic side of
  `query`. This tool's own channel scoping is applied inline in `query` text
  instead (see the tool description), not through `modifiers`, for that
  reason — don't pass `in:` here either.
- Reach for this whenever the request names something specific enough to
  paste literally — a ticket key, an identifier, a proper noun — rather than
  trusting `query` alone to carry it and hoping semantic matching doesn't
  drift onto something adjacent-but-wrong.

### Semantic vs keyword

Semantic matching is on by default and helps when the user's words differ from
the channel's words — "why was the deploy rolled back" finding "we reverted
because the migration locked the table."

Set `disable_semantic_search: true` when you need **exact token matching**:

- error codes, stack trace fragments, ticket keys
- specific identifiers, hostnames, config keys
- any case where a near-miss is worse than no match

Semantic matching can rank a topically similar message above an exact hit, which
is the wrong trade when the user handed you a literal string.

### Parameters worth setting deliberately


| Parameter                   | Set it to                                                                      | Reason                                                                                                                                                                                                                                                                 |
| --------------------------- | ------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `channel_ids`               | Omit for unscoped; a list of resolved IDs to restrict to specific channels     | A list, even for one channel. All must be within your allowlist — if even one isn't, the whole call is rejected before Slack is ever called, nothing partial comes back                                                                                                |
| `exclude_channel_ids`       | A list of IDs to search every allowed channel except those                     | For when one channel dominates unscoped results, whether with no signal or with signal that's burying the rest — see "The search loop for unscoped questions" above. Mutually exclusive with `channel_ids`; same all-or-nothing whitelist check                        |
| `include_context_messages`  | `true` for almost every question                                               | A bare hit is a fragment. Surrounding messages are how you tell a question from its answer, or a proposal from a decision. They come back inline in each result as `context — user: text` lines immediately before/after the matched message — highest-value flag here |
| `limit`                     | 10–20                                                                          | Max is 20. Use the headroom; a second page costs a call                                                                                                                                                                                                                |
| `sort`                      | `score` by default, `timestamp` for "latest"/"most recent"                     | Relevance and recency are different questions                                                                                                                                                                                                                          |
| `include_bots`              | `false` unless the answer is plausibly from a bot (CI, alerts, error tracking) | Bot chatter crowds out humans. When bot messages are included, results tag them `[bot]` so you don't mistake one for a human answering                                                                                                                                 |
| `action_token`              | Pass it through whenever this search follows a message event                   | Bot-token calls require it; omitting it fails the call rather than returning fewer results                                                                                                                                                                             |
| `include_archived_channels` | `true` for historical questions                                                | Archived channels are where old decisions go                                                                                                                                                                                                                           |
| `highlight`                 | `true` when you'll quote or cite                                               | Shows which terms actually matched, so you can tell a real hit from a semantic stretch                                                                                                                                                                                 |
| `content_types`             | Leave as `messages`                                                            | `files` and `channels` results carry no channel ID to check, so they aren't supported                                                                                                                                                                                  |




### If the first query misses

Reformulate — don't repeat. The same query returns the same results. In order of
what usually works:

1. **Drop the least distinctive word.** Four terms → two.
2. **Try the team's vocabulary, not the user's.** They said "authentication
  issue"; the channel probably says "SSO" or "login loop."
3. **Widen or remove the time window.**
4. **Flip semantic mode.** Semantic returned adjacent-but-wrong things → disable
  it and search the literal string. Exact search returned nothing → let semantic
   try.
5. **Drop or widen** `channel_ids` if you had scoped it. You may have guessed
  wrong about where the conversation happened — remove the scope entirely, or
  add more channels, rather than assuming the topic just isn't there.

Three or four reformulations is a reasonable ceiling.

### The search loop for unscoped questions

Treat an unscoped search as a loop, not a single call: **search → analyze →
decide → repeat**, until either the question is answerable from what you've
accumulated, or you've genuinely run out of room to search further.
Reformulating the query (previous subsection) and excluding a channel are two
moves inside this *same* loop, not separate procedures — which one you reach
for depends on what the last round actually showed you.

Each round, classify what came back before deciding the next move:


| What the round showed                              | What that means                                                               | Next move                                                                                                                                                            |
| -------------------------------------------------- | ----------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Hits spread across several channels, some relevant | You have signal and no single channel is skewing it                           | **Stop the loop.** Read the promising hits and answer.                                                                                                               |
| Nothing relevant, spread across several channels   | A genuine miss, not a channel problem                                         | **Reformulate** (the ladder above), same channel scope, next round                                                                                                   |
| Nothing relevant, dominated by one channel         | That channel is high-volume, not informative, for this query                  | **Exclude that channel** (`exclude_channel_ids` set to its ID), keep or reformulate the query, next round                                                            |
| Relevant hits, but dominated by one channel        | That channel answered something, but its volume may be burying other channels | **Accumulate** those hits into your running answer, **then exclude that channel anyway** and search again — don't stop just because one channel had something to say |


Repeat until one of two things ends the loop:

1. **A round comes back with nothing new to add, and nothing left worth
  excluding.** What you've accumulated across rounds is the answer — move on
  to reading the hits you've gathered and answering from them.
2. **Excluding the next dominant channel would exhaust the whitelist** —
  `search_whitelisted_channels` refuses that call outright rather than
  running it (there's nothing left to search). Treat that as the hard stop.
  Report whatever you *did* accumulate before hitting it, and name which
  channels you had to exclude and why — don't present the gap as "nothing
  exists." This is the same honesty rule as "Before claiming nothing exists"
  below, just reached via exclusion instead of reformulation.

Two failure modes to avoid:

- **Stopping the instant one channel looks bad**, without checking whether
it's dominating with nothing (exclude and keep going) or dominating with
something real (accumulate, then still keep going) — both cases move to
another round; only "spread and empty" or "spread and relevant" end the loop.
- **Excluding channels forever without ever accumulating anything**, chasing
an ever-shrinking whitelist instead of noticing you've already got an
answer. If a round's hits would answer the question, stop there —
exhausting every channel isn't the goal, answering the question is.

The reformulation ceiling (three or four differently-phrased queries) still
bounds how many times you change the *query*; it's a separate axis from
exclusion, which is naturally bounded by the whitelist shrinking to nothing.
A loop that reformulates twice and excludes twice has used its reformulation
budget once each way — it hasn't run four reformulations.

---



## Step 4: Read what you found



### `conversations_history` — the channel skeleton

Returns **top-level messages only, newest first, paged.** Thread replies are not
included. Lean on this: it gives you a channel's shape cheaply, and you then
expand only the threads that matter.

`limit` is a **string** taking either a duration or a count:

- `"1d"`, `"7d"`, `"1w"`, `"30d"`, `"90d"` — time window
- `"50"` — message count
- Default `"1d"`
- **Must be empty when you pass** `cursor`**.** Passing both errors out.

Prefer a duration when the user gave a time frame ("since Monday" → `"7d"`), a
count when they didn't.

Keep `include_activity_messages: false`. Join/leave noise is never the answer and
eats your window.

### `conversations_replies` — the thread

Takes `channel_id` and `thread_ts` (format `1234567890.123456`, the parent
message's timestamp). Same `limit`/`cursor` rules.

**Expand a thread when** its top-level message is on-topic and has meaningful
reply volume, or poses a question whose answer must be below it. **Don't** expand
every thread in a channel — that's the token sink this two-tier design exists to
prevent. Read the skeleton, pick two or three threads, expand those.

### Reading discipline

- **Note what you didn't see.** If you read `"50"` messages of a channel that
clearly has more, "nobody mentioned X" is unsupported. Either page further with
`cursor` or scope the claim to what you read.
- **Track who said what.** A suggestion is not a decision. Someone floating
"maybe we should move to Postgres" is not the team deciding to. Before
reporting that something was decided, check that someone actually said so; if
the evidence is a proposal, report it as a proposal.
- **Paraphrase by default, quote briefly.** Quote only when exact wording changes
the meaning — a commitment, a number, a precise instruction.
- **Prefer the later statement.** If a channel discussed something twice and
reversed itself, lead with the current position and note the change.

When citing Slack evidence, what makes it checkable is **channel, approximate
date, and author** — not just the message text.

---



## Handling failures

Most bad answers here come from mishandled failures rather than bad queries. The
cardinal rule:

> **A failure is never a finding.** A call that errored tells you nothing about
> whether the content exists. Only an *empty successful result* is evidence of
> absence.

Conflating the two is the worst outcome available to you: the user asks whether
something was discussed, a call fails, and you report that nothing was discussed.
They then act on a false negative. Always check whether you got an error or an
empty result set before characterising what's in Slack.

### Classify first, then respond

Every failure falls into one of three buckets, and each gets different treatment:


| Bucket             | Examples                                                                                                             | Treatment                                                          |
| ------------------ | -------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| **Self-caused**    | Bad parameter combination, wrong `thread_ts` format, unresolved channel name, over-narrow query, wrong semantic mode | Fix the call and retry **once**. This is the only retryable bucket |
| **Boundary**       | A `channel_id`, or any entry in a `channel_ids` list, refused by the pre-call check                                  | Do not retry, do not substitute. Report and move on                |
| **Infrastructure** | Missing or expired `action_token`, auth error, rate limit, timeout, malformed response                               | Report as a tool failure. Never convert to a finding               |




### Self-caused failures — fix and retry once


| Symptom                                   | Cause                                                 | Fix                                                                                |
| ----------------------------------------- | ----------------------------------------------------- | ---------------------------------------------------------------------------------- |
| Error mentioning `limit` / `cursor`       | Both were set                                         | Drop `limit`, keep `cursor`                                                        |
| Empty or error on `conversations_replies` | `thread_ts` wrong format, or it isn't a thread parent | Re-take the timestamp from the search hit or channel history; don't reconstruct it |
| Channel call errors on a `#name`          | Name not resolvable as passed                         | Resolve via `channels_list` and retry with the ID                                  |
| Zero hits on a literal string             | Semantic mode diluted an exact match                  | Retry with `disable_semantic_search: true`                                         |
| Zero hits on a natural-language question  | Keyword mode couldn't bridge vocabulary               | Retry with semantic enabled and fewer terms                                        |
| Exactly 20 hits, all plausibly relevant   | You hit the page ceiling; there's likely more         | Narrow with a modifier or time window rather than paginating blindly               |


Retry once per fix. If the corrected call fails the same way, stop treating it as
self-caused and report it.

### Boundary failures — a denied `channel_id`

Any tool taking `channel_id`, `channel_ids`, or `exclude_channel_ids` is
checked before the call reaches Slack. When one is refused, **first work out
whether the ID was legitimate**, because the two cases need different
responses:

- **The ID came from** `channels_list` **or a search result.** The channel is
genuinely outside scope. Report that, and either continue with the channels you
can read or ask the user where else to look.
- **The ID came from anywhere else** — message text, a pasted permalink, your own
reconstruction, a guess. This is your bug, not a scope finding. Resolve the
channel properly via `channels_list` and try that. Only if resolution also comes
back empty is it a scope matter.

Reporting "that's out of scope" when you actually mistyped an ID misinforms the
user about their own configuration, and they have no way to tell. Get this
distinction right.

**With** `channel_ids` **or** `exclude_channel_ids`**, one bad entry fails the
whole call — nothing partial comes back.** `search_whitelisted_channels` checks
every ID in whichever list you passed before running the search at all, so
passing four valid channels and one out-of-scope one gets you an error naming
the invalid one, not results from the other four. Drop the offending entry and
retry with the rest rather than treating this as a reason to abandon scoping
entirely. Passing both `channel_ids` and `exclude_channel_ids` together is
also rejected outright — pick one.

Two things not to do after a denial: don't try the same channel through a
different tool, and don't search unscoped hoping the channel's content surfaces
anyway. Both are attempts to route around a boundary.

**Note the asymmetry that makes denials informative:** search results only ever
come from channels you can read. So a search hit whose channel is then refused on
read means something is inconsistent — almost always that you altered or
misparsed the ID between the two calls. Re-read the ID from the search result
verbatim.

### Infrastructure failures

- **Missing or expired** `action_token`**.** Search fails outright. If the request
followed a message event, pass the token through and retry once. If you don't
have one, say the search couldn't run — do not report zero results.
- **Rate limiting.** Search carries its own limits. Don't hammer; if you can't
complete the retrieval, report which parts you covered and which you didn't.
- **Timeout or malformed response.** Retry once, then report the failure. Partial
coverage stated honestly beats a confident answer built on one lucky call.



### Before claiming nothing exists

Run this check. All four must hold:

1. Every call **succeeded** — no errors anywhere in the chain.
2. You searched **unscoped**, so all readable channels were covered.
3. You tried at least **two differently-phrased queries**, including a flip of
  semantic mode.
4. Your **time window** was wide enough for the question, or absent.

If any of these fails, your answer isn't "nothing exists" — it's "here's what I
covered and what I couldn't." Name the queries you tried and the window you used,
so the user can redirect you:

> No results for "rate limiting" or "throttling" across the channels I can read,
> going back to April. Different wording, or a channel outside my scope, would
> both explain that.



### Partial success

Common and easy to mishandle: search succeeds, one of three thread reads fails.
Answer from the two that worked and say the third couldn't be read. Don't silently
drop it — a gap the user knows about is manageable; one they don't is a trap.

---

**Read-directly** — location already known: a named channel, a given thread, a
pasted link, or the current channel/thread from context:

1. Resolve only what context doesn't already cover (e.g. a *different* channel
  named in the question)
2. Read straight away — `conversations_history`, `conversations_replies`, or
  `conversations_unreads` — no search step at all
3. Answer

Go deeper on either shape when the question genuinely has multiple parts —
search or read each part separately, since a combined query/read returns
shallow coverage for all of them — or when the first search missed and
reformulation is warranted.

**Stop when every part of the question is grounded in something you actually
retrieved**, not at a call count. Check the question clause by clause before
answering; if you were about to supply a figure, name, or date from memory rather
than from a result, search or read for it instead.

**Stop searching** when three or four differently-phrased queries have returned
nothing useful. More attempts produce noise, not answers. That ceiling is
specific to *search* reformulation — it's not a reason to cut a read short (e.g.
stop paging `conversations_history` before covering the window the question
actually asked about).

---



## Known gaps in this tool set

Don't claim coverage you don't have:

- **No pinned-message tool.** Channels often pin the canonical answer — runbook,
policy, current owner. You can't see pins. If a question smells like it has a
pinned canonical answer and search isn't finding it, say pinned content is
outside your reach and suggest checking the channel's pins.
- **No canvases or bookmarks.** Teams park durable reference material there. Same
handling as pins.
- **No cross-session search.** You can't full-text search your own past sessions.
If continuity matters, ask for the thread or the timeframe.
- `saved_list` **is the authenticated user's saved items**, not a channel's pins.
Don't substitute one for the other.
- `attachment_get_data` **may be inert.** It's gated server-side by an
environment variable independent of tool configuration. If a file's contents
matter and the call fails, report that file contents aren't reachable rather
than guessing from the filename.

---



## Worked examples

The channels, people, services, and ticket keys below are **placeholders chosen to
show the shape of each move**. They are not real entities in this workspace — never
carry a name or an identifier from these examples into an actual tool call, and
never assume a channel, service, or ticket format exists because it appears here.

**"Did anyone ever figure out why the export endpoint 500s on a missing field?"**

1. `search_whitelisted_channels`, unscoped — query `export endpoint missing
  field`,` include_context_messages: true`, semantic left on (the user's wording
   probably differs from the channel's).
2. Two hits in one channel, both top-level messages with replies.
3. `conversations_replies` on both, using the `thread_ts` values from the hits
  verbatim.
4. Answer: the diagnosis, who reached it, when, whether a fix landed. If the
  thread trails off unresolved, say it trails off unresolved.

**"Catch me up on the deploy channel since Monday."**

1. `channels_list` → resolve to an ID.
2. `conversations_history`, `limit: "7d"`.
3. Scan the skeleton; expand the two or three threads with real reply volume.
4. Group by topic, not chronologically — a chronological dump is what they were
  avoiding by asking. Flag anything waiting on someone.

**"What's the state of ticket EXAMPLE-1234?"** (whatever key format this team
actually uses — take it from the user's message, don't invent one)

1. `search_whitelisted_channels`, unscoped — query the key exactly as the user
  wrote it, `disable_semantic_search: true` (exact key; semantic would surface
   related-but-different tickets), `sort: timestamp`, `sort_dir: desc` — the
   *latest* mention is what "state" means.
2. Read the most recent hit's thread.
3. Answer with the current position, noting earlier contradicting statements.

**"Who should I ask about the nightly test pipeline?"**

1. `search_whitelisted_channels`, unscoped — query `nightly test pipeline`,
  `include_context_messages: true`.
2. Note who *answers* questions about it across hits, not who asks.
3. `users_search` to resolve the handle. If that comes back empty,
  `search_users_directory` on the same name before giving up on resolving it.
4. Answer, labelling it as inference from who's been answering — because that's
  what it is.

**"Has Jen looked at the export bug?" — the name matches more than one person.**

1. `search_whitelisted_channels`, unscoped — query `export bug`, one relevant
  hit in `#eng-support`.
2. `users_search` for `Jen` returns nothing (no literal substring match on
  anyone's profile) — fall back to `search_users_directory`.
3. Two exact matches: "Jennifer Hynes" and "Jenna Ruiz." Ambiguous — pass
  `channel_id: eng-support` (the channel the question is actually about) to
  the same call to disambiguate.
4. One of the two is flagged `in_channel: true`. Lead with that one, but say
  so explicitly rather than presenting it as certain — membership is a signal,
  not proof of identity.

**"Who's in the on-call channel right now?"**

1. `channels_list` → resolve the name to an ID.
2. `list_channel_members` on that ID — real names come back directly, no
  further resolution needed.
3. Answer with the list, noting it's a current snapshot if the question
  implies "who's been on-call" over time rather than right now.

**"Did we ever discuss the database migration in either the platform or infra
channel?"** — named channels, more than one.

1. `channels_list` → resolve both names to IDs.
2. `search_whitelisted_channels` with `channel_ids: [<platform-id>, <infra-id>]`
  (not two separate single-channel searches) — one ranked, pooled result set
  across both, so whichever channel talks more doesn't bury the other's hits.
3. Read the threads that matter from either channel.
4. Answer, citing which of the two channels each point came from.

**"What have people said about the new pricing model?" — one channel keeps
dominating with nothing relevant.**

1. `search_whitelisted_channels`, unscoped — query `pricing model`. Ten hits,
  eight from `#C_random_placeholder`, none on-topic (that channel is just
  chatty).
2. Reformulate once — `pricing tiers`, still mostly the same channel, still
  nothing relevant.
3. That's two reformulated unscoped searches with the same channel dominating
  and no signal — stop reformulating. Retry unscoped with
  `exclude_channel_ids: [C_random_placeholder]`, using the ID straight off the
  hits already seen, not a guess.
4. This time the remaining channels' hits surface. Read and answer from those.

**"Did we ever settle on a vendor for the offsite?" — one channel dominates,**
**and this time it's actually relevant.**

1. `search_whitelisted_channels`, unscoped — query `offsite vendor`. Seven of
  nine hits are from `#events-planning`, and they're on-topic — this channel
  isn't noise, it's just where the conversation happened.
2. Don't stop here. Accumulate these hits as candidate answers, then retry
  with `exclude_channel_ids: [<events-planning-id>]` to check whether any
  other channel also has something to add that `#events-planning`'s volume
  was crowding out of the first round's ranking.
3. The exclusion retry surfaces one more relevant hit from `#finance` (budget
  sign-off) that hadn't made the first page. Accumulate that too.
4. A third round would exclude `#finance` as well, but nothing new comes back
  spread thin across whatever remains — that's the stop condition. Read the
  threads from both channels and answer from the combined set, citing which
  channel each part came from.

**Failure case: the user names a channel you can't reach.**

1. `channels_list` → no match, or a match whose ID the pre-call check refuses.
2. Don't retry, don't pick a similarly-named channel, don't search unscoped and
  present the results as if they came from the named channel.
3. Report that the channel is out of scope, then offer what you *can* do: search
  the channels you can read for the same terms. Often that answers the question
   anyway.

