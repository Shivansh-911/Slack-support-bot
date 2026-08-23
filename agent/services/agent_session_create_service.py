"""Creates or reuses the Claude Managed Agents session backing an agent run.

A session that finishes its work stays `idle` rather than terminating, so the
session behind an earlier run in the same Slack thread is still usable for a
follow-up mention. Reusing it keeps that thread's conversation history and
sandbox intact; a fresh session is only created when no usable one exists.
"""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class AgentSessionCreateService:
    REUSABLE_STATUSES = ('idle', 'running')

    def _reuse(self, client, session_id):
        try:
            session = client.beta.sessions.retrieve(session_id)
        except Exception:
            return None
        if session.status not in self.REUSABLE_STATUSES:
            return None
        return session.id

    def _create(self, client, channel_id, thread_ts):
        self._assert_configured()
        session = client.beta.sessions.create(
            agent=settings.CMA_AGENT_ID,
            environment_id=settings.CMA_ENVIRONMENT_ID,
            vault_ids=[settings.CMA_VAULT_ID] if settings.CMA_VAULT_ID else [],
            budget=self._budget(),
            title=self._title(channel_id, thread_ts),
            resources=self._resources(),
        )
        return session.id

    def _resources(self):

        if not settings.CMA_SLACK_MEMORY_STORE_ID:
            return []
        if not settings.CMA_WHITELISTED_CHANNELS:
            return []
        return [
            # CMA_SLACK_MEMORY_STORE_ID => per-channel/per-user context files.
            # Mount path is NOT hardcoded here — CMA auto-injects the real
            # mount path, access mode, and this instructions text into the
            # session's system prompt, so the agent always sees the correct
            # live path rather than one we guessed.
            {
                'type': 'memory_store',
                'memory_store_id': settings.CMA_SLACK_MEMORY_STORE_ID,
                'access': 'read_write',
                'instructions': (
                    "Holds one file per channel and per user: "
                    "channel:{channel_id}.md and user:{user_id}.md. "
                    ""
                    "channel:{channel_id}.md covers: the channel's name, its "
                    "purpose, how it's used, and other durable facts about "
                    "it. "
                    "user:{user_id}.md covers: the person's name, role, which "
                    "channels they're present in, their projects, and other "
                    "durable facts about them. "
                    ""
                    "1. Before resolving a channel or user, check here first "
                    "— an existing file means you don't need to re-resolve it "
                    "from scratch. "
                    "2. After resolving new information about a channel or "
                    "user, reconcile it against that file: "
                    "if it already says the same thing, leave the file "
                    "alone; if it contradicts what's on file, update just "
                    "the contradicted part in place — don't leave old and "
                    "new claims both standing, and don't rewrite the whole "
                    "file; if it's new and not already captured, append it "
                    "under the relevant heading; if no file exists yet, "
                    "create one using the format above. "
                    "3. If a single fact involves both a channel and a user "
                    "(e.g. a person's role in that channel), write it to "
                    "both files — don't record it in only one place. "
                    "4. Never overwrite a file wholesale; only ever touch "
                    "the specific line or section a piece of new "
                    "information affects."
                )
            },
            # CMA_WHITELISTED_CHANNELS => single read-only allowlist file,
            # channels.md, listing every Slack channel_id (and its name) this
            # agent may access. Read at the start of every conversation.
            {
                'type': 'memory_store',
                'memory_store_id': settings.CMA_WHITELISTED_CHANNELS,
                'access': 'read_only',
                'instructions': (
                    "Contains a single file, channels.md, listing every Slack "
                    "channel_id (and its name) this agent is allowed to "
                    "access. "
                    "1. Read it once at the start of every conversation, "
                    "before the first Slack tool call. "
                    "2. Before calling any Slack tool that takes a "
                    "channel_id, confirm that id appears in this file first — "
                    "if it doesn't, treat the channel as out of scope rather "
                    "than calling the tool."
                )
            }
        ]

    def _budget(self):
        return {
            'type': 'limit',
            'max_list_cost': {
                'amount': str(settings.CMA_SESSION_BUDGET_CENTS),
                'currency': 'USD',
            },
        }

    def _title(self, channel_id, thread_ts):
        if thread_ts:
            return f'Slack thread {channel_id}/{thread_ts}'
        return f'Slack channel {channel_id}'

    def _assert_configured(self):
        missing = [
            name
            for name in ('CMA_AGENT_ID', 'CMA_ENVIRONMENT_ID')
            if not getattr(settings, name, None)
        ]
        if missing:
            raise ImproperlyConfigured(
                f'{", ".join(missing)} must be set before starting a session. '
                'Create the agent and environment with the `ant` CLI first.'
            )

