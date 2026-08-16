"""Handles inbound agent run requests raised from Slack events.

Confirmable tool calls (`agent.mcp_tool_use`) go through `AgentToolGateService`,
which allows or denies based on the channel whitelist. Custom tool calls
(`agent.custom_tool_use`) go through `AgentCustomToolService` instead, which
actually executes the tool — unlike MCP tools, nothing runs a custom tool but
the client, so there is no confirmation step to gate.
"""

from agent.exceptions import SessionBusyError
from agent.models.session import Session
from agent.services.anthropic_client_service import AnthropicClientService
from agent.services.agent_session_create_service import AgentSessionCreateService
from agent.services.agent_tool_gate_service import AgentToolGateService
from agent.services.agent_custom_tool_service import AgentCustomToolService


class AgentRunService:
    REQUIRES_ACTION = 'requires_action'

    def handle_run(self, channel_id, channel_name, thread_ts, team_id, user_id, question):

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
                client, session_id, channel_id, channel_name, thread_ts, user_id, question
            )
        finally:
            Session.objects.mark_idle(session)

    def _drive(self, client, session_id, channel_id, channel_name, thread_ts, user_id, question):
        tool_gate = AgentToolGateService()
        custom_tool_service = AgentCustomToolService()
        texts = []

        with client.beta.sessions.events.stream(session_id) as stream:


            self._send(client, session_id, {
                "type": "user.message",
                "content": [{
                    "type": "text",
                    "text": self._context_message(
                        channel_id, channel_name, thread_ts, user_id, question
                    ),
                }],
            })

            for event in stream:
                reply = self._handle_event(event, texts, tool_gate, custom_tool_service)
                if reply is not None:
                    self._send(client, session_id, reply)
                if self._is_finished(event):
                    break
        return '\n\n'.join(texts).strip()

    def _send(self, client, session_id, event):
        return client.beta.sessions.events.send(session_id, events=[event])

    def _context_message(self, channel_id, channel_name, thread_ts, user_id, question):
        return (
            '[Slack context]\n'
            f'channel_id: {channel_id}\n'
            f'channel_name: {channel_name}\n'
            f'thread_ts: {thread_ts}\n'
            f'user_id: {user_id}\n\n'
            f'{question}'
        )


    def _handle_event(self, event, texts, tool_gate, custom_tool_service):
        if event.type == 'agent.message':
            texts.extend(self._text_blocks(event))
        elif event.type == 'agent.mcp_tool_use':
            return tool_gate.handle_mcp_tool_use(event)
        elif event.type == 'agent.custom_tool_use':
            return custom_tool_service.handle_custom_tool_use(event)
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
