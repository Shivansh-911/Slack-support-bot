"""Executes generic custom tools that carry no Slack/Asana scope of their
own — the utility counterpart to AgentAsanaCustomToolService /
AgentslackCustomToolService, which delegates any tool name this class
`handles()` to it.
"""

import json

from agent.services.utility.current_time_service import CurrentTimeService


class AgentUtilityCustomToolService:

    def __init__(self):
        self._handlers = {
            'get_current_time': self._handle_get_current_time,
        }

    def handles(self, tool_name):
        return tool_name in self._handlers

    def handle_custom_tool_use(self, event):
        return self._handlers[event.name](event)

    def _handle_get_current_time(self, event):
        result = CurrentTimeService().get_current_time()
        return self._reply(event, result)

    def _reply(self, event, result):
        if isinstance(result, dict) and result.get('error'):
            return self._result(event, result['error'], is_error=True)
        return self._result(event, json.dumps(result, indent=2, default=str))

    def _result(self, event, text, is_error=False):
        reply = {
            'type': 'user.custom_tool_result',
            'custom_tool_use_id': event.id,
            'content': [{'type': 'text', 'text': text}],
        }
        if is_error:
            reply['is_error'] = True
        return reply


__all__ = ['AgentUtilityCustomToolService']
