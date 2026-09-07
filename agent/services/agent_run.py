"""Handles inbound agent run requests raised from Slack events.

Confirmable tool calls (`agent.mcp_tool_use`) go through `AgentMcpToolGateService`,
which allows or denies based on the channel whitelist. Custom tool calls
(`agent.custom_tool_use`) go through `AgentAsanaCustomToolService`/
`AgentslackCustomToolService` instead, which actually execute the tool — unlike
MCP tools, nothing runs a custom tool but the client, so there is no
confirmation step to gate.

`team` and `all_channels` come from the caller (SlackEventListenerService),
which has already resolved which team this message belongs to and fetched
that team's live channel whitelist — this file never re-derives either one,
so there is exactly one place per run that decides team scope.

`agent.message` text is buffered as it streams, never posted as it arrives —
the caller only gets back the single final answer once the run ends, so it
alone decides what reaches Slack.
"""

from django.utils import timezone

from agent.exceptions import SessionBusyError
from agent.models.session import Session
from agent.services.anthropic_client_service import AnthropicClientService
from agent.services.agent_session_create_service import AgentSessionCreateService
from agent.services.agent_mcp_tool_gate_service import AgentMcpToolGateService
from agent.services.slack.agent_slack_custom_tool_service import AgentslackCustomToolService
from agent.services.asana.agent_asana_custom_tool_service import AgentAsanaCustomToolService


class AgentRunService:
    REQUIRES_ACTION = 'requires_action'

    def handle_run(self, channel_id, thread_ts, team_id, user_id, question, message_ts, trigger_type, team, all_channels):
        session = Session.objects.existing_session(team_id, channel_id, thread_ts)
        if session and session.status == Session.Status.RUNNING:
            raise SessionBusyError(session)

        client = AnthropicClientService().build()
        agent_session_create_service = AgentSessionCreateService()

        session_id = None
        if session and session.cma_session_id:
            session_id = agent_session_create_service._reuse(client, session.cma_session_id)

        if session_id is None:
            session_id = agent_session_create_service._create(client, channel_id, thread_ts, team)
            session = Session.objects.create(team_id, channel_id, thread_ts, session_id, team.name)

        try:
            Session.objects.mark_running(session)
            return self._drive(
                client, session_id, channel_id, thread_ts, user_id, question, message_ts,
                trigger_type, team, all_channels,
            )
        finally:
            session_details = client.beta.sessions.retrieve(session_id=session_id)
            Session.objects.session_stop(session, session_details)

    def _drive(self, client, session_id, channel_id, thread_ts, user_id, question, message_ts, trigger_type, team, all_channels):
        tool_gate = AgentMcpToolGateService()
        slack_tool_service = AgentslackCustomToolService(team)
        asana_tool_service = AgentAsanaCustomToolService(team)
        final_text_blocks = []

        with client.beta.sessions.events.stream(session_id) as stream:

            self._send(client, session_id, {
                "type": "user.message",
                "content": [{
                    "type": "text",
                    "text": self._context_message(
                        channel_id, thread_ts, user_id, question, message_ts, trigger_type, all_channels, team
                    ),
                }],
            })

            for event in stream:
                reply = self._handle_event(event, tool_gate, slack_tool_service, asana_tool_service, all_channels)
                if reply is not None:
                    self._send(client, session_id, reply)
                if event.type == 'agent.message':
                    final_text_blocks = self._text_blocks(event) or final_text_blocks
                if self._is_finished(event):
                    break

        return '\n\n'.join(final_text_blocks)

    def _send(self, client, session_id, event):
        return client.beta.sessions.events.send(session_id, events=[event])

    def _context_message(self, channel_id, thread_ts, user_id, question, message_ts, trigger_type, all_channels, team):
        return (
            "[Scope for this run — everything you may access]\n"
            f"Allowed Slack channels: {all_channels}\n"
            f"Allowed Asana workspace: {team.asana_workspace_gid}\n"
            f"Allowed Asana projects: {team.asana_project_gids}\n\n"
            "[Slack context — where this question was posted, not where to search]\n"
            f"channel_id: {channel_id}\n"
            f"thread_ts: {thread_ts}\n"
            f"message_ts: {message_ts}\n"
            f"user_id: {user_id}\n"
            f"trigger: {trigger_type}\n"
            f"current_datetime: {self._current_datetime()}  "
            "(authoritative — use this, not message_ts or ambient guesswork, "
            "for any freshness/staleness comparison against memory, and for "
            "any freshness cutoff you pass to a specialist)\n\n"
            "Don't restrict your search to the channel above unless the question "
            "itself names that channel (or says \"this channel,\" \"here,\" etc.).\n\n"
            "[Question]\n"
            f"{question}\n\n"

            "[Reminders]\n"
            "- Before writing the final answer, read the standing-instructions "
            "memory store in full — every time, even if you already read it "
            "earlier in this session — and shape tone/format/length to match "
            "what it says. Do this before reconciling anything else.\n"
            "- Also reconcile relevant memory for this channel, thread, and "
            "user. Treat memory as context that may be incomplete or stale, "
            "and prioritize the current conversation when the two conflict.\n"
            "- Don't include any memory-reconciliation marker or internal "
            "reasoning in the final answer.\n"
            "- Only your last message this turn reaches the user — anything "
            "said earlier in the turn is discarded, not shown."
        )

    def _current_datetime(self):
        # Minute-level precision, fixed UTC label (settings.TIME_ZONE) — no
        # local/implicit timezone, no seconds; both would add ambiguity
        # rather than remove it.
        return timezone.now().strftime('%Y-%m-%d %H:%M UTC (%A)')

    def _handle_event(self, event, tool_gate, slack_tool_service, asana_tool_service, all_channels):
        if event.type == 'agent.mcp_tool_use':
            return tool_gate.handle_mcp_tool_use(event, all_channels)
        elif event.type == 'agent.custom_tool_use':
            if asana_tool_service.handles(event.name):
                return asana_tool_service.handle_custom_tool_use(event)
            if slack_tool_service.handles(event.name):
                return slack_tool_service.handle_custom_tool_use(event, all_channels)
        return None

    def _is_finished(self, event):
        """Idle alone is not terminal — it is also how a session waits on us."""
        if event.type == 'session.status_terminated':
            return True
        if event.type != 'session.status_idle':
            return False
        return getattr(event.stop_reason, 'type', None) != self.REQUIRES_ACTION

    def _text_blocks(self, event):
        return [
            block.text
            for block in getattr(event, 'content', None) or []
            if getattr(block, 'type', '') == 'text' and getattr(block, 'text', '')
        ]


__all__ = ['AgentRunService']
