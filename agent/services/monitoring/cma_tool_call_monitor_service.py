"""Records one New Relic `CmaToolCall` custom event per tool call the
server runs for a CMA session, and times each one as its own step
(`CmaTool/<tool name>`) inside the Slack question's trace — so the Slack
and Asana API calls a tool makes show up nested under it.

Built once per agent run by `AgentRunService.handle_run`. `_drive` passes
every stream event through `observe`, which learns which session thread
belongs to which agent from the `agent_name` the `session.thread_*` events
carry, and runs every tool through `track`. Custom tool calls only carry
their `session_thread_id`, so this mapping is what attributes each call to
the subagent that made it.

Custom events carry no link to the transaction they were recorded in, so
each event copies the ids a dashboard needs to join back: the trace id,
the CMA session/thread/tool-use ids, and the Slack question's ids. Tool
failures here are almost never Python exceptions — the tool services
return `{'error': ...}` and build a reply with `is_error` set — so the
reply itself is what decides `tool.is_error`. The running
`tool_call_count`/`tool_error_count` are copied onto the question's
`SlackQuestion` event once the run stops.
"""

import json
import logging
import time

import newrelic.agent


logger = logging.getLogger(__name__)


class CmaToolCallMonitorService:
    EVENT_TYPE = 'CmaToolCall'
    TRACE_GROUP = 'CmaTool'
    TOOL_TYPES = {
        'agent.custom_tool_use': 'custom',
        'agent.mcp_tool_use': 'mcp',
    }
    TARGET_UNHANDLED = 'unhandled'

    def __init__(self, session_id, team, channel_id, thread_ts, message_ts, user_id):
        self.session_id = session_id
        self.team = team
        self.channel_id = channel_id
        self.thread_ts = thread_ts
        self.message_ts = message_ts
        self.user_id = user_id
        self.tool_services = {}
        self.agent_names_by_thread = {}
        self.tool_call_count = 0
        self.tool_error_count = 0

    def register_tool_services(self, tool_services):
        self.tool_services = tool_services

    def observe(self, event):
        thread_id = getattr(event, 'session_thread_id', None)
        agent_name = getattr(event, 'agent_name', None)
        if thread_id and agent_name:
            self.agent_names_by_thread[thread_id] = agent_name

    def track(self, event, run_tool):
        if event.type not in self.TOOL_TYPES:
            return run_tool()
        started_at = time.monotonic()
        try:
            with newrelic.agent.FunctionTrace(name=event.name, group=self.TRACE_GROUP):
                reply = run_tool()
        except Exception as error:
            self._record(event, None, self._elapsed_ms(started_at), str(error))
            raise
        self._record(event, reply, self._elapsed_ms(started_at), None)
        return reply

    def _record(self, event, reply, duration_ms, raised_error):
        try:
            result_text = self._result_text(reply)
            is_error = raised_error is not None or bool(reply and reply.get('is_error'))
            self.tool_call_count += 1
            if is_error:
                self.tool_error_count += 1
            thread_id = getattr(event, 'session_thread_id', None)
            tool_input = getattr(event, 'input', None) or {}
            newrelic.agent.record_custom_event(self.EVENT_TYPE, {
                'tool.name': event.name,
                'tool.type': self.TOOL_TYPES[event.type],
                'tool.target': self._target(event),
                'tool.input': json.dumps(tool_input, default=str),
                'tool.channel': tool_input.get('channel') or tool_input.get('channel_id'),
                'tool.duration_ms': round(duration_ms, 1),
                'tool.is_error': is_error,
                'tool.error_message': raised_error or (result_text if is_error else None),
                'tool.result_size': len(result_text) if result_text is not None else None,
                'tool.decision': reply.get('result') if reply else None,
                'cma.session_id': self.session_id,
                'cma.thread_id': thread_id,
                'cma.agent_name': self.agent_names_by_thread.get(thread_id),
                'cma.tool_use_id': event.id,
                'slack.message_ts': self.message_ts,
                'slack.thread_ts': self.thread_ts,
                'slack.channel_id': self.channel_id,
                'slack.user_id': self.user_id,
                'slack.agent_team': self.team.name,
                'trace.id': newrelic.agent.current_trace_id(),
            })
        except Exception:
            logger.warning('Could not record New Relic tool call event', exc_info=True)

    def _target(self, event):
        if event.type == 'agent.mcp_tool_use':
            return f"mcp:{getattr(event, 'mcp_server_name', '')}"
        for target, service in self.tool_services.items():
            if service.handles(event.name):
                return target
        return self.TARGET_UNHANDLED

    def _result_text(self, reply):
        if not reply:
            return None
        return '\n'.join(
            block.get('text', '')
            for block in reply.get('content') or []
            if block.get('type') == 'text'
        )

    def _elapsed_ms(self, started_at):
        return (time.monotonic() - started_at) * 1000


__all__ = ['CmaToolCallMonitorService']
