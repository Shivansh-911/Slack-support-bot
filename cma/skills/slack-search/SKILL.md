---
name: slack-search
description: Search Slack with search_whitelisted_channels first, before any other Slack tool. Use for anything Slack-related — "check Slack", "did anyone mention X", "what's the status of X", "search channel for Y", "what did I miss", "what did I save", "who's in team X". Read-only.
---

# Slack Search

## Strategy

1. **Review the query first.** Work out the intent and pull out the actual keywords before touching
   any tool — don't just forward the raw question as a search string. The intent decides which of
   the branches below applies; most queries are plain keyword/topic search (step 5) but check for
   the more specific cases first.
2. **If the query names a person** (a display name, not a Slack user ID), resolve them with
   `users_search` before doing anything else. You need the resolved identity to file a `from:`
   filter correctly and to refer to them by their real name in the answer, rather than guessing at
   spelling or quietly dropping the person filter. If it doesn't resolve, don't block the rest of
   the search on it — fall through to the steps below using the name as plain free text instead.
3. **If the query names a user group / subteam** instead of (or alongside) a person — "who's on
   @backend-team", "ping the design squad" — resolve the handle with `usergroups_list` the same
   way: get the real group and its membership before answering, rather than guessing who's in it.
4. **If the query is specifically about saved items** ("what did I save", "show my saved
   messages/reminders"), go straight to `saved_list` — don't route this through channel search at
   all, it isn't channel content.
5. **If the query is about unread or missed messages** ("what did I miss", "anything new since
   yesterday") across channels generally rather than one named channel, use `conversations_unreads`
   directly instead of searching.
6. **If the channel is already known** (the user names it, or it's evident from the conversation
   you're replying in), skip straight to `conversations_history` on it. If the gate refuses it,
   that means it's out of scope — say so and stop, don't try another tool to reach it.
7. **Otherwise, start with `search_whitelisted_channels`** for keyword/topic questions rather than
   pulling full channel histories blind. It's already scoped to what you're allowed to see. If step
   2 or 3 resolved a person or group, add `from:<their handle>` to the query.
8. **Drill into replies mechanically.** For every match with `reply_count > 0`, pull the thread
   with `conversations_replies` — regardless of whether the parent message reads like a
   discussion-starter. A one-line message can anchor the longest thread in the channel.
9. **An empty search result is not proof the topic was never discussed.** It may use different
   wording, or live in a channel outside your allowlist. Say that plainly rather than concluding
   "nothing was found anywhere." If it's worth another pass, try `channels_me` first — channels
   you're actually a member of are a better proxy for real read access than the full workspace list
   — then `channels_list` as a broader fallback. Either way, showing up there still isn't
   permission to read it; try `conversations_history` on the candidate and let the gate decide.
10. **For "what happened today/recently" questions on a known channel**, go straight to
    `conversations_history` with a bounded recent window rather than searching.
11. **If you do pull a full or wide `conversations_history` range**, remember it's newest-first with
    no relevance ranking of its own — a capped pull silently drops everything older than the cap,
    with no error telling you it happened. Pull the full range the question actually needs.


## Tool guide

**`search_whitelisted_channels`** is the default tool for anything Slack-related. It's a free-text
search already restricted server-side to the channels you're allowed to read
(`SlackChannelSearchService` drops every match outside the allowlist before you see it), so a
result appearing here needs no permission check from you. Slack's modifiers work (`from:`,
`before:`, `after:`, etc.) except `in:`/channel scoping, which the server enforces regardless of
the query. `conversations_search_messages` (the MCP tool) isn't available to you at all — this is
the replacement for it, not a fallback.

**`conversations_replies`** drills into a thread once search (or a channel read) surfaces a match
with replies.

**`conversations_history`** reads a channel directly when you already know which one — newest
first, with no relevance ranking of its own. A capped pull silently drops everything older than
the cap, so pull the full range the question needs.

**`channels_me`** and **`channels_list`** are both last resorts, only after search comes up empty
and you need a candidate channel name. Try `channels_me` first — it's scoped to channels you're
actually a member of, which tracks real read access more closely than the full workspace list — then
`channels_list` if that comes up short. Either way, showing up in either list is not permission to
read it; try `conversations_history` on the candidate and let the gate decide.

**`users_search`** works in both directions: resolve a name to an ID up front when the query
mentions a person (so you can filter with `from:`), and resolve an ID back to a display name before
you quote anyone. If it doesn't resolve either way, fall back to plain free text for the search, or
say "user `<ID>`" when quoting — never invent a name.

**`usergroups_list`** resolves an @group/subteam handle the same way `users_search` resolves a
person — use it when the query names a team/group rather than an individual, before answering who's
in it or filtering search by it.

**`saved_list`** answers "what did I save" / "show my saved items" directly. It's not channel
content, so don't route these through `search_whitelisted_channels` or `conversations_history`.

**`conversations_unreads`** answers "what did I miss" across channels generally. Use it instead of
search when the question is about unread/new activity rather than a specific topic or keyword.

No write tools are available. `conversations_add_message`, `reactions_add`, `reactions_remove`,
`conversations_mark`, `conversations_leave`, `conversations_join`, `usergroups_create`,
`usergroups_update`, `usergroups_users_update`, `usergroups_me`, `saved_update`, and
`saved_clear_completed` are all denied. If asked to post, react, join/leave a channel, edit a
group, or change a saved item's status, say plainly that you can only read Slack.

## Access boundary

You can only read messages from an allowlisted set of channels, enforced in code
(`AgentToolGateService` for the MCP read tools, `SlackChannelSearchService` for search) rather than
by these instructions — expect it regardless. A gate refusal is a boundary, not an error: don't
retry it, don't reach for another tool to route around it, and tell the user plainly the channel is
out of scope. If a tool call fails for another reason (missing scope, rate limit, bot not in a
channel), report the actual error and stop rather than improvising a raw API or token workaround.

## Answering

Lead with the answer, then the evidence — link the specific messages you relied on, with
permalinks. Group by channel if more than one is involved. If nothing turns up, say so plainly and
describe what you checked.
