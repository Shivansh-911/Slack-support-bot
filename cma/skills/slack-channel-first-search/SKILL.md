---
name: slack-channel-first-search
description: >-
  Primary Slack retrieval strategy. Resolve channels, people, and usergroup/team
  references before retrieving messages, then read applicable channel history
  directly. Use this for all Slack questions. If no channel is specified, inspect
  all channels this agent can read. There is no search fallback.
---

# Slack Channel-First Search

Use direct Slack channel reads for every Slack question.

Before reading messages, resolve any entities relevant to the question:
- channel
- person
- Slack usergroup
- natural-language team/group

Then retrieve messages from the applicable channels.

## 1. Determine Scope

### Channel

- Explicit channel → scope to that channel.
- No channel → scope to every channel returned by `list_channels`.
- Call `list_channels` once per conversation and reuse the result.

### Person

If a person is mentioned:

- Resolve them with `users_search`.
- Prefer the closest unambiguous match.
- If no match is found, continue without a person constraint.

A resolved person is a **channel-membership constraint**.

### Usergroup / Team

A reference to a team, group, squad, department, function, or collective may refer to a Slack usergroup.

Examples:
- `@backend-team`
- "backend team"
- "platform team"
- "infra team"
- "CX team"
- "engineering team"

For each such reference:

1. Call `usergroups_list`.
2. Match against the usergroup `handle` and `name`.
3. Prefer:
   - exact handle
   - exact name
   - closest unambiguous match.
4. If matched, retain its member user IDs.
5. If no match is found, continue using the original wording as a normal relevance/topic signal.

Do not hardcode workspace-specific usergroups.

A resolved usergroup represents its members for **relevance and attribution**. It is not an author.

**Usergroup membership must never be used to include or exclude channels.**

## 2. Person Membership Gate

Only a resolved person creates a channel-membership gate.

If a person was resolved:

- Call `list_conversation_members` for each channel before reading its history.
- If the person is a member → read the channel.
- If the person is not a member → skip the channel.

Do not infer membership from messages.

If no person was specified, no membership check is required.

For multiple channels, check membership independently for every channel.

## 3. Read Channel History

For each channel that passes the person membership check:

Call `conversations_history`.

### Time range

- If the question specifies a timeframe, use a duration covering it, such as `"7d"` or `"30d"`.
- If no timeframe is specified, use a count-based `limit` and paginate with `cursor` until `has_more` is false.
- Do not assume a fixed duration such as `"90d"` is sufficient.
- Keep `include_activity_messages: false`.

Read top-level messages first. Do not fetch every thread.

## 4. Identify Relevant Messages

Use top-level history to identify:

- messages related to the requested topic
- messages authored by the resolved person
- messages authored by members of a resolved usergroup
- relevant participants
- decisions versus proposals
- threads that contain useful discussion
- high-reply or otherwise relevant messages

For a resolved usergroup, its member IDs are the people representing that group.

Do not attribute a message to the usergroup itself.

If the team/group did not resolve to a usergroup, use the original wording and surrounding context as the relevance signal.

## 5. Expand Relevant Threads

Use `conversations_replies` only for relevant top-level messages.

Prioritize:

1. Messages directly related to the question.
2. Messages authored by the resolved person.
3. Messages authored by members of the resolved usergroup.
4. Threads containing decisions, useful discussion, or important context.

Do not fetch unrelated threads.

## 6. Resolve Names

Before attributing or quoting a message:

- Use `get_user_profile` for the relevant user ID.
- Never expose a bare Slack user ID.
- Resolve only users whose identity is needed for the answer.

For usergroup questions, attribute statements to the actual member who wrote them.

## 7. Multi-Channel Queries

If multiple channels are in scope:

1. Apply the person membership check, if applicable.
2. Read history for channels that pass.
3. Identify relevant messages.
4. Expand relevant threads.
5. Resolve required user names.
6. Continue to the next channel.

Do not reuse person membership results between channels.

Usergroup membership does not affect channel scope.

## 8. No Results or Errors

If the complete applicable scope has been checked and nothing relevant was found, report that plainly.

If a natural-language team/group did not match a Slack usergroup:

- Do not conclude that the team/group does not exist.
- Continue retrieval using the original wording.

A tool error is not evidence of absence. Surface the error instead of reporting "nothing found."

Do not claim that a channel or usergroup does not exist unless the corresponding resolution tool was actually called and returned no match.

## Examples

**"What did @backend-team discuss?"**

→ Resolve the usergroup → inspect all readable channels → identify messages from its members → expand relevant threads.

**"What did the platform team handle this month?"**

→ Check whether "platform team" matches a Slack usergroup → if matched, use its members for relevance → inspect the requested timeframe across readable channels.

**"What did the platform team discuss in #deploy?"**

→ Resolve the usergroup → scope to `#deploy` → use its members to identify relevant messages.

**"Did Alex and the platform team discuss deployment?"**

→ Resolve Alex and the platform team independently → use Alex as a channel-membership constraint → use platform-team members only for relevance and attribution.

**"What happened in #deploy?"**

→ Resolve the channel → read its history.

**"Has anyone discussed the new pricing model?"**

→ No channel/person/group constraint → inspect all readable channels.