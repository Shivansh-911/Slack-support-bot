"""Executes Slack-related custom tool calls and builds the
`user.custom_tool_result` reply.

Dispatches `agent.custom_tool_use` events by tool name to the service that
actually runs them. Mirrors AgentAsanaCustomToolService's shape: one
`_handle_*` method per tool, each pulling its own fields off `event.input`
explicitly and passing them by name.
"""

import json

from agent.services.slack.slack_channel_search_assistant_service import SlackChannelSearchAssistantService
from agent.services.slack.slack_channel_members_service import SlackChannelMembersService
from agent.services.slack.slack_user_profile_service import SlackUserProfileService
from agent.services.slack.slack_channel_service import SlackChannelService


class AgentslackCustomToolService:

    def __init__(self):
        self._handlers = {
            'search_whitelisted_channels': self._handle_search,
            'list_conversation_members': self._handle_list_conversation_members,
            'get_user_profile': self._handle_get_user_profile,
            'list_channels': self._handle_list_channels,
        }

    def handles(self, tool_name):
        return tool_name in self._handlers

    def handle_custom_tool_use(self, event, channel_mapping=None):
        return self._handlers[event.name](event, channel_mapping)

    def _handle_search(self, event, channel_mapping):
        _ = channel_mapping
        result = SlackChannelSearchAssistantService().search(
            query=event.input.get('query'),
            channel_ids=event.input.get('channel_ids'),
            exclude_channel_ids=event.input.get('exclude_channel_ids'),
            action_token=event.input.get('action_token'),
            include_bots=event.input.get('include_bots'),
            include_deleted_users=event.input.get('include_deleted_users'),
            before=event.input.get('before'),
            after=event.input.get('after'),
            include_context_messages=event.input.get('include_context_messages'),
            context_channel_id=event.input.get('context_channel_id'),
            cursor=event.input.get('cursor'),
            sort=event.input.get('sort'),
            sort_dir=event.input.get('sort_dir'),
            include_message_blocks=event.input.get('include_message_blocks'),
            highlight=event.input.get('highlight'),
            term_clauses=event.input.get('term_clauses'),
            modifiers=event.input.get('modifiers'),
            include_archived_channels=event.input.get('include_archived_channels'),
            disable_semantic_search=event.input.get('disable_semantic_search'),
            channel_mapping=channel_mapping
        )
        return self._reply(event, result)

    def _handle_list_conversation_members(self, event, channel_mapping):
        result = SlackChannelMembersService().members(event.input.get('channel_id'))
        return self._reply(event, result)

    def _handle_get_user_profile(self, event, channel_mapping):
        result = SlackUserProfileService().get_user(event.input.get('user_id'))
        return self._reply(event, result)

    def _handle_list_channels(self, event, channel_mapping):
        mapping = SlackChannelService()._fetch_id_to_name()
        result = [{'channel_id': channel_id, 'name': name} for channel_id, name in mapping.items()]
        return self._reply(event, result)

    def _reply(self, event, result):
        if isinstance(result, dict) and result.get('error'):
            return self._result(event, result['error'], is_error=True)
        if isinstance(result, list) and not result:
            return self._result(event, 'No results found.')
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


__all__ = ['AgentslackCustomToolService']
