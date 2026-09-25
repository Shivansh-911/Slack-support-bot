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

Streaming `agent.message` text straight to Slack as it arrives is disabled
(see `_drive` below) — `on_agent_message` is no longer called per event.
Instead `handle_run` returns the last non-empty `agent.message` text once
the session finishes, and the caller posts that single final answer itself
— this file never calls the Slack API directly.

`handle_run` also returns `did_react`: whether the orchestrator called
`add_reaction` this turn. The orchestrator's own instructions treat
reacting (instead of answering) as a deliberate zero-output turn, so the
caller uses this flag to tell that intentional silence apart from a run
that simply failed to produce text — the two cases both leave
`final_answer` empty, but only one of them warrants a fallback message.

New Relic monitoring hooks in at two points, both in
`agent/services/monitoring/`: the caller's `SlackQuestionMonitorService`
collects the CMA session used, what this turn cost (session total now
minus `Session.usage` from before the run) and the tool totals for the
question's `SlackQuestion` event, and every tool event in `_drive` runs
through `CmaToolCallMonitorService`, which times it and records one
`CmaToolCall` event per call.
"""

from django.utils import timezone

from agent.exceptions import SessionBusyError
from agent.models.session import Session
from agent.services.anthropic_client_service import AnthropicClientService
from agent.services.agent_session_create_service import AgentSessionCreateService
from agent.services.agent_mcp_tool_gate_service import AgentMcpToolGateService
from agent.services.slack.agent_slack_custom_tool_service import AgentslackCustomToolService
from agent.services.asana.agent_asana_custom_tool_service import AgentAsanaCustomToolService
from agent.services.utility.agent_utility_custom_tool_service import AgentUtilityCustomToolService
from agent.services.monitoring.slack_question_monitor_service import SlackQuestionMonitorService
from agent.services.monitoring.cma_tool_call_monitor_service import CmaToolCallMonitorService


class AgentRunService:
    REQUIRES_ACTION = 'requires_action'

    def handle_run(self, channel_id, thread_ts, team_id, user_id, question, message_ts, trigger_type, team, all_channels, on_agent_message, channel_type=None, context=None, question_monitor=None):
        question_monitor = question_monitor or SlackQuestionMonitorService()
        session = Session.objects.existing_session(team_id, channel_id, thread_ts)
        if session and session.status == Session.Status.RUNNING:
            raise SessionBusyError(session)

        client = AnthropicClientService().build()
        agent_session_create_service = AgentSessionCreateService()

        session_id = None
        if session and session.cma_session_id:
            session_id = agent_session_create_service._reuse(client, session.cma_session_id)

        session_reused = session_id is not None
        if not session_reused:
            session_id = agent_session_create_service._create(client, channel_id, thread_ts, team)
            session = Session.objects.create(team_id, channel_id, thread_ts, session_id, team.name)

        question_monitor.add_session_fields(session_id, session_reused, team.cma_agent_id)
        tool_monitor = CmaToolCallMonitorService(session_id, team, channel_id, thread_ts, message_ts, user_id)
        previous_session_cost = session.usage

        try:
            Session.objects.mark_running(session)
            final_answer, did_react = self._drive(
                client, session_id, channel_id, thread_ts, user_id, question, message_ts,
                trigger_type, team, all_channels, on_agent_message, tool_monitor, channel_type, context,
            )
        finally:
            session_details = client.beta.sessions.retrieve(session_id=session_id)
            Session.objects.session_stop(session, session_details)
            question_monitor.add_cost_fields(previous_session_cost, session_details)
            question_monitor.add_tool_counts(tool_monitor.tool_call_count, tool_monitor.tool_error_count)

        return final_answer, did_react

    def _drive(self, client, session_id, channel_id, thread_ts, user_id, question, message_ts, trigger_type, team, all_channels, on_agent_message, tool_monitor, channel_type=None, context=None):
        tool_gate = AgentMcpToolGateService()
        slack_tool_service = AgentslackCustomToolService(team, channel_type)
        asana_tool_service = AgentAsanaCustomToolService(team)
        utility_tool_service = AgentUtilityCustomToolService()
        tool_monitor.register_tool_services({
            'slack': slack_tool_service,
            'asana': asana_tool_service,
            'internal': utility_tool_service,
        })

        with client.beta.sessions.events.stream(session_id) as stream:

            self._send(client, session_id, {
                "type": "user.message",
                "content": [{
                    "type": "text",
                    "text": self._context_message(
                        channel_id, thread_ts, user_id, question, message_ts, trigger_type, all_channels, team, context
                    ),
                }],
            })

            final_answer = ''
            for event in stream:
                tool_monitor.observe(event)
                reply = tool_monitor.track(
                    event,
                    lambda: self._handle_event(event, tool_gate, slack_tool_service, asana_tool_service, utility_tool_service, all_channels),
                )
                if reply is not None:
                    self._send(client, session_id, reply)
                if event.type == 'agent.message':
                    text_blocks = self._text_blocks(event)
                    if text_blocks:
                        final_answer = '\n\n'.join(text_blocks)
                        # Streaming to Slack per-event is disabled — only the
                        # final answer is posted, once, by the caller.
                        # on_agent_message(final_answer)
                if self._is_finished(event):
                    break

        return final_answer, slack_tool_service.did_react

    def _send(self, client, session_id, event):
        return client.beta.sessions.events.send(session_id, events=[event])

    def _context_message(self, channel_id, thread_ts, user_id, question, message_ts, trigger_type, all_channels, team, context=None):
        context_section = f"[Context]\n{context}\n\n" if context else ''
        return (
            "[Scope for this run everything you may access]\n"
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
            f"{context_section}"
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

    def _handle_event(self, event, tool_gate, slack_tool_service, asana_tool_service, utility_tool_service, all_channels):
        if event.type == 'agent.mcp_tool_use':
            return tool_gate.handle_mcp_tool_use(event, all_channels)
        elif event.type == 'agent.custom_tool_use':
            if asana_tool_service.handles(event.name):
                return asana_tool_service.handle_custom_tool_use(event)
            if slack_tool_service.handles(event.name):
                return slack_tool_service.handle_custom_tool_use(event, all_channels)
            if utility_tool_service.handles(event.name):
                return utility_tool_service.handle_custom_tool_use(event)
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
