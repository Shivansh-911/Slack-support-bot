"""Executes Slack-related custom tool calls and builds the
`user.custom_tool_result` reply.

Dispatches `agent.custom_tool_use` events by tool name to the service that
actually runs them. Mirrors AgentAsanaCustomToolService's shape: one
`_handle_*` method per tool, each pulling its own fields off `event.input`
explicitly and passing them by name.

Every tool's single-channel field is named `channel` by convention, so
`handle_custom_tool_use` gates it once, here, against the run's channel
whitelist (`channel_mapping`) before dispatch — any future single-channel
tool gets this check for free just by naming its field `channel`. The one
exception is `search_whitelisted_channels`: its `channel_ids` is a list, so
a single bad entry shouldn't reject the whole call the way Asana's
workspace/project gate does. `_handle_search` filters that list down to the
whitelisted subset itself and notes what got dropped, only erroring out if
nothing in the list was in scope.
"""

import json

from agent.services.slack.slack_channel_search_assistant_service import SlackChannelSearchAssistantService
from agent.services.slack.slack_channel_members_service import SlackChannelMembersService
from agent.services.slack.slack_user_profile_service import SlackUserProfileService
from agent.services.slack.slack_channel_service import SlackChannelService
from agent.services.slack.slack_usergroups_service import SlackUserGroupsService
from agent.services.slack.slack_reactions_service import SlackReactionsService


class AgentslackCustomToolService:

    def __init__(self):
        self._handlers = {
            'search_whitelisted_channels': self._handle_search,
            'list_conversation_members': self._handle_list_conversation_members,
            'get_user_profile': self._handle_get_user_profile,
            'list_channels': self._handle_list_channels,
            'list_usergroups': self._handle_list_usergroups,
            'add_reaction': self._handle_add_reaction,
        }

    def handles(self, tool_name):
        return tool_name in self._handlers

    def handle_custom_tool_use(self, event, channel_mapping):
        channel = event.input.get('channel')
        if channel is not None and channel not in channel_mapping:
            return self._reply(event, {'error': f'Channel {channel} is not whitelisted.'})
        return self._handlers[event.name](event, channel_mapping)

    def _handle_search(self, event, channel_mapping):
        channel_ids = event.input.get('channel_ids')
        out_of_scope = []
        if channel_ids:
            out_of_scope = [c for c in channel_ids if c not in channel_mapping]
            channel_ids = [c for c in channel_ids if c in channel_mapping]
            if not channel_ids:
                return self._reply(event, {'error': 'None of the requested channel_ids are whitelisted.'})

        context_channel_id = event.input.get('context_channel_id')
        if context_channel_id and context_channel_id not in channel_mapping:
            return self._reply(event, {'error': f'Channel {context_channel_id} is not whitelisted.'})

        result = SlackChannelSearchAssistantService().search(
            query=event.input.get('query'),
            channel_ids=channel_ids,
            # exclude_channel_ids=event.input.get('exclude_channel_ids'),
            # action_token=event.input.get('action_token'),
            include_bots=event.input.get('include_bots'),
            include_deleted_users=event.input.get('include_deleted_users'),
            before=event.input.get('before'),
            after=event.input.get('after'),
            include_context_messages=event.input.get('include_context_messages'),
            context_channel_id=context_channel_id,
            cursor=event.input.get('cursor'),
            sort=event.input.get('sort'),
            sort_dir=event.input.get('sort_dir'),
            # include_message_blocks=event.input.get('include_message_blocks'),
            # highlight=event.input.get('highlight'),
            term_clauses=event.input.get('term_clauses'),
            modifiers=event.input.get('modifiers'),
            # include_archived_channels=event.input.get('include_archived_channels'),
            disable_semantic_search=event.input.get('disable_semantic_search'),
            channel_mapping=channel_mapping
        )
        return self._reply(event, result, out_of_scope)

    def _handle_list_conversation_members(self, event, channel_mapping):
        result = SlackChannelMembersService().members(event.input.get('channel'))
        return self._reply(event, result)

    def _handle_get_user_profile(self, event, channel_mapping):
        result = SlackUserProfileService().get_user(event.input.get('user_id'))
        return self._reply(event, result)

    def _handle_list_channels(self, event, channel_mapping):
        mapping = SlackChannelService()._fetch_id_to_name()
        result = [{'channel_id': channel_id, 'name': name} for channel_id, name in mapping.items()]
        return self._reply(event, result)

    def _handle_list_usergroups(self, event, channel_mapping):
        result = SlackUserGroupsService().list_with_members()
        return self._reply(event, result)

    def _handle_add_reaction(self, event, channel_mapping):
        result = SlackReactionsService().add_reaction(
            channel_id=event.input.get('channel'),
            timestamp=event.input.get('timestamp'),
            emoji_name=event.input.get('emoji_name'),
        )
        return self._reply(event, result)


    def _reply(self, event, result, out_of_scope=None):
        if isinstance(result, dict) and result.get('error'):
            return self._result(event, result['error'], is_error=True)
        if isinstance(result, list) and not result:
            return self._result(event, 'No results found.')
        text = json.dumps(result, indent=2, default=str)
        if out_of_scope:
            text += f"\n\nNote: these channel_ids were not whitelisted and were excluded from the search: {', '.join(out_of_scope)}"
        return self._result(event, text)

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
