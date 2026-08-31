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
        resources = []

        if settings.CMA_SLACK_MEMORY_STORE_ID:
            # CMA_SLACK_MEMORY_STORE_ID => per-channel/per-user context files.
            # Mount path is NOT hardcoded here — CMA auto-injects the real
            # mount path, access mode, and this instructions text into the
            # session's system prompt, so the agent always sees the correct
            # live path rather than one we guessed.
            resources.append({
                'type': 'memory_store',
                'memory_store_id': settings.CMA_SLACK_MEMORY_STORE_ID,
                'access': 'read_write',
                'instructions': (
                    "Holds durable facts about Slack channels and users. "
                    "Before resolving a channel or user, check here first, "
                    "case-insensitively — reuse what's already recorded "
                    "instead of re-resolving from scratch. When new info "
                    "arrives, update an existing entry in place rather than "
                    "duplicating it; only touch the part that changed."
                )
            })

        if settings.CMA_WHITELISTED_CHANNELS:
            # CMA_WHITELISTED_CHANNELS => single read-only allowlist file,
            # channels.md, listing every Slack channel_id (and its name) this
            # agent may access. Read at the start of every conversation.
            resources.append({
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
            })

        if settings.CMA_INSTRUCTIONS_MEMORY_STORE_ID:
            # CMA_INSTRUCTIONS_MEMORY_STORE_ID => standing instructions a user
            # has given the agent about how to behave and format answers.
            # Global to the whole workspace, not scoped to a channel or user.
            resources.append({
                'type': 'memory_store',
                'memory_store_id': settings.CMA_INSTRUCTIONS_MEMORY_STORE_ID,
                'access': 'read_write',
                'instructions': (
                    "Holds standing instructions a user has given about how "
                    "you should behave and format answers in this workspace "
                    "— tone, response length, formatting, things to always "
                    "or never do. These apply globally, not to one channel "
                    "or user. Read it before answering every message and "
                    "shape your response accordingly. When someone gives you "
                    "an instruction meant to apply going forward rather than "
                    "just this once, write it here — update an existing "
                    "entry in place if it conflicts with or refines one "
                    "already recorded, rather than duplicating it."
                )
            })

        return resources

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

