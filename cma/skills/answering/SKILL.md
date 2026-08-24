---
name: answering
description: >-
  Run this as the LAST step before delivering any answer based on retrieved
  evidence. It is a strict confidence and answer-scope gate. It decides
  whether the evidence supports the answer and removes all information that
  was not explicitly requested.
---

# Answer Confidence Gate

This is the final gate before the response is sent.

The goal is NOT to summarize the research. The goal is to answer the user's
question with only the information the question asks for.

## Step 1: Identify the question type

Determine what the user is asking for:

| Type | Final answer may contain |
|---|---|
| When | Date/time/timeframe |
| Where | Location |
| Who | Person/team/entity |
| What | The requested thing/value |
| Why | Reason/cause |
| How | Mechanism/steps |
| Whether | Yes/no + the minimum fact needed to establish it |
| Other/open-ended | Answer only what was explicitly requested |

For compound questions, answer each requested part.

Do NOT add related facts simply because they were found during retrieval.

## Step 2: Check confidence

Ask:

- Does the retrieved evidence directly support the answer?
- Is the interpretation unambiguous?
- Would a reasonable reader reach the same conclusion?
- Am I filling any gap with an assumption?

If the evidence does not support a confident answer, do not guess.

A large amount of related evidence does not increase confidence if none of
it directly answers the question.

If sources conflict on the answer itself (e.g. Slack and Asana disagree, or
two messages contradict), the conflict IS the answer — state both values
briefly rather than silently picking one or pruning one out as unrequested.

## Step 3: High confidence

If the evidence supports the answer:

1. Keep only the information required by the question type.
2. Remove all retrieval/process narration.
3. Remove supporting facts that were not requested.
4. Remove related dates, people, tasks, channels, status information, and
   background unless explicitly requested.
5. Do not explain how the answer was found.
6. Keep the evidence's actual certainty and verb — don't upgrade a proposal
   into a decision or a mention into a commitment while trimming.
7. Never output a raw Slack/Asana ID — a bare `U0…`/`C0…`/`T0…` string, or
   an Asana `gid`. A person or channel appears by name, a task/project by
   its name (with the Asana permalink, per the Final rule below). If an ID
   is all you have, that's a retrieval gap to close now, before drafting
   the answer — not something to pass through and fix up after:
   - **Slack user ID** → call `get_user_profile` with that ID, use the
     resolved name.
   - **Slack channel ID** → resolve it against the channel list already
     fetched via `list_channels` earlier this conversation (see the
     slack-context-search skill) rather than re-fetching.
   - **Asana gid** → the Asana tool call that returned it almost always
     carried a `name` alongside the `gid` — use that. If you only kept the
     bare gid, fetch it (`asana_get_task` / `asana_get_project` / etc.)
     before answering.
   Resolve every ID the answer will mention before you write the draft, not
   as a pass to clean up after — an ID left in a draft is easy to forget to
   swap out.
8. If the answer names or references an Asana task or project, its
   `permalink_url` must appear right alongside the name — e.g. `Fix login
   bug (https://app.asana.com/0/…)`. This holds for every task the answer
   mentions, not just the primary one, and survives step 3.4's trimming:
   the permalink isn't "extra information" being added back in, it's part
   of how the task is named. The Asana tool call that returned the task
   almost always carried `permalink_url` alongside `name`/`gid` — carry it
   forward with the task. If you only kept the bare name or gid, fetch the
   task (`asana_get_task` / `asana_get_project`) to get its permalink
   before answering — do this at the same time as the ID resolution in
   item 7, not as a separate pass after the draft.

## Step 4: Low confidence

If the evidence does not provide a confident answer, output ONLY a concise
statement that no confident answer was found.

Do not include:

- closest matches
- related facts
- search results
- task names
- dates from related activity
- people involved
- channel names
- explanations of what was searched
- speculation
- hedged guesses

### Example

Question:
"When was the CDS/CMS API key implementation?"

Retrieved evidence:
- An Asana task is still in progress.
- Nitish discussed rotating existing keys on July 30.
- No confirmed launch date exists.

Final answer:

"Couldn't find a confirmed implementation date."

Do NOT output the Asana task, July 30 message, people involved, channel names,
or the task status unless the user asks for those details.

## Final rule

The retrieved evidence is used to determine the answer, NOT to determine
what additional information should be shown, except for the Asana
permalink rule in step 3.8, which always applies whenever an Asana task
or project is named.

Answer the question asked — not the research performed.