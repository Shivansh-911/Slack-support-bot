"""Handles inbound agent run requests raised from Slack events.

Confirmable tool calls (`agent.mcp_tool_use`) go through `AgentToolGateService`,
which allows or denies based on the channel whitelist. Custom tool calls
(`agent.custom_tool_use`) go through `AgentCustomToolService` instead, which
actually executes the tool — unlike MCP tools, nothing runs a custom tool but
the client, so there is no confirmation step to gate.

`agent.message` text is buffered as it streams, never posted as it arrives —
the caller only gets back the single final answer once the run ends, so it
alone decides what reaches Slack.
"""

from agent.exceptions import SessionBusyError
from agent.models.session import Session
from agent.services.anthropic_client_service import AnthropicClientService
from agent.services.agent_session_create_service import AgentSessionCreateService
from agent.services.agent_mcp_tool_gate_service import AgentMcpToolGateService
from agent.services.slack.agent_slack_custom_tool_service import AgentslackCustomToolService
from agent.services.slack.slack_channel_service import SlackChannelService
from agent.services.asana.agent_asana_custom_tool_service import AgentAsanaCustomToolService
from config import settings


class AgentRunService:
    REQUIRES_ACTION = 'requires_action'
    channel_mapping = None 

    def handle_run(self, channel_id, thread_ts, team_id, user_id, question):
        self.channel_mapping = SlackChannelService()._fetch_id_to_name()

        print(self.channel_mapping)

        session = Session.objects.find_by_thread(team_id, channel_id, thread_ts)
        if session and session.status == Session.Status.RUNNING:
            raise SessionBusyError(session)

        client = AnthropicClientService().build()
        agent_session_create_service = AgentSessionCreateService()

        session_id = None
        if session and session.cma_session_id:
            session_id = agent_session_create_service._reuse(client, session.cma_session_id)
            #session_id can be null if terminated session, need to handle that
        else:
            session_id = agent_session_create_service._create(client, channel_id, thread_ts)
            session = Session.objects.create(team_id, channel_id, thread_ts, session_id)

        try:
            Session.objects.mark_running(session)
            return self._drive(
                client, session_id, channel_id, thread_ts, user_id, question
            )
        finally:
            session_details = client.beta.sessions.retrieve(session_id=session.cma_session_id)
            Session.objects.session_stop(session, session_details)
            # Session.objects.mark_idle(session)

    def _drive(self, client, session_id, channel_id, thread_ts, user_id, question):
        tool_gate = AgentMcpToolGateService()
        final_text_blocks = []

        with client.beta.sessions.events.stream(session_id) as stream:


            self._send(client, session_id, {
                "type": "user.message",
                "content": [{
                    "type": "text",
                    "text": self._context_message(
                        channel_id, thread_ts, user_id, question
                    ),
                }],
            })

            for event in stream:
                reply = self._handle_event(event, tool_gate)
                if reply is not None:
                    self._send(client, session_id, reply)
                if event.type == 'agent.message':
                    final_text_blocks = self._text_blocks(event) or final_text_blocks
                if self._is_finished(event):
                    break

        return '\n\n'.join(final_text_blocks)

    def _send(self, client, session_id, event):
        return client.beta.sessions.events.send(session_id, events=[event])

    def _context_message(self, channel_id, thread_ts, user_id, question):
        return (
            "[Slack context — where this question was posted, not where to search]\n"
            f"channel_id: {channel_id}\n"
            f"thread_ts: {thread_ts}\n"
            f"user_id: {user_id}\n\n"
            "Don't restrict your search to the channel above unless the question "
            "itself names that channel (or says \"this channel,\" \"here,\" etc.).\n\n"
            "[Question]\n"
            f"{question}\n\n"
    
            "[Reminders]\n"
            "- Before writing the final answer, reconcile relevant memory for "
            "this channel, thread, and user. Treat memory as context that may "
            "be incomplete or stale, and prioritize the current conversation "
            "when the two conflict.\n"
            "- Don't include any memory-reconciliation marker or internal "
            "reasoning in the final answer.\n"
            "- Only your last message this turn reaches the user — anything "
            "said earlier in the turn is discarded, not shown."
        )


    def _handle_event(self, event, tool_gate):
        if event.type == 'agent.mcp_tool_use':
            return tool_gate.handle_mcp_tool_use(event, self.channel_mapping)
        elif event.type == 'agent.custom_tool_use':
            asana_custom_tool_service = AgentAsanaCustomToolService()
            if asana_custom_tool_service.handles(event.name):
                return asana_custom_tool_service.handle_custom_tool_use(event)
            slack_custom_tool_service = AgentslackCustomToolService()
            if slack_custom_tool_service.handles(event.name):
                return slack_custom_tool_service.handle_custom_tool_use(event, self.channel_mapping)
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



