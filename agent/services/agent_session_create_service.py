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
        )
        return session.id

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

