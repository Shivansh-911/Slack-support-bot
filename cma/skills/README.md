# Skills

Each subdirectory here is one skill, in the standard Skill format: a
`SKILL.md` at its root (name + description in frontmatter, instructions in
the body), plus any supporting files it references.

    cma/skills/
      some-skill/
        SKILL.md
        reference.md      # optional, only loaded if SKILL.md points to it

These are not read by anything at runtime on their own — they are source.
Run `cma/scripts/upload_skills.sh` to push them to the Skills API
(`ant beta:skills` / `ant beta:skills:versions`), which prints the
`skill_id` + version each one gets. Put those into `cma/agent.yaml`'s
`skills:` list, then run `cma/scripts/sync_agent.sh` to apply the agent
definition.

`.manifest.json` (created on first upload, gitignored) maps each skill
folder name to the `skill_id` the API assigned it, so re-running the upload
script for a folder that already exists creates a new version instead of a
duplicate skill.

`slack-search/` is the first skill: how to use this agent's Slack tools
(`search_whitelisted_channels`, `channels_list`, `conversations_history`,
`conversations_replies`, `users_search`) — search-first strategy, the
allowlist boundary, and the read-only rule. Not yet uploaded (see below) or
wired into `cma/agent.yaml`'s `skills:` list.

`asana-search/` covers the Asana `asana_*` MCP tools (`asana_search_tasks`,
`asana_get_tasks_for_project`, `asana_get_my_tasks`, `asana_get_task`, and the
rest) — which ones carry a workspace/project field the code gate can check,
which don't (and so must only ever be called on a gid already surfaced by a
scoped result), and the read-only rule. Not yet uploaded or wired into
`cma/agent.yaml`'s `skills:` list.
