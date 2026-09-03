"""Executes Slack-related custom tool calls and builds the
`user.custom_tool_result` reply.

Dispatches `agent.custom_tool_use` events by tool name to the service that
actually runs them. Mirrors AgentAsanaCustomToolService's shape: one
`_handle_*` method per tool, each pulling its own fields off `event.input`
explicitly and passing them by name. Every underlying Slack call goes out
under this instance's own team's seat token — the team this instance was
built with is fixed for its whole lifetime, so there is no way for one
team's tool call to run under another team's identity.

Every tool's single-channel field is named `channel` by convention, so
`handle_custom_tool_use` gates it once, here, against the run's channel
whitelist (`channel_mapping`) before dispatch — any future single-channel
tool gets this check for free just by naming its field `channel`. There
are two exceptions. `search_whitelisted_channels`: its `channel_ids` is a
list, so a single bad entry shouldn't reject the whole call the way
Asana's workspace/project gate does — `_handle_search` filters that list
down to the whitelisted subset itself and notes what got dropped, only
erroring out if nothing in the list was in scope. `add_reaction`: it acts
on whatever channel/message the Slack event already told it about, not a
retrieval target chosen by the agent, so the whitelist (which scopes
search) doesn't apply to it.
"""

import json

from agent.services.slack.slack_channel_search_assistant_service import SlackChannelSearchAssistantService
from agent.services.slack.slack_conversation_history_service import SlackConversationHistoryService
from agent.services.slack.slack_conversation_replies_service import SlackConversationRepliesService
from agent.services.slack.slack_channel_members_service import SlackChannelMembersService
from agent.services.slack.slack_user_profile_service import SlackUserProfileService
from agent.services.slack.slack_channel_service import SlackChannelService
from agent.services.slack.slack_usergroups_service import SlackUserGroupsService
from agent.services.slack.slack_reactions_service import SlackReactionsService
from agent.services.slack.formatter.slack_search_result_formatter import SlackSearchResultFormatter
from agent.services.slack.formatter.slack_conversation_history_formatter import SlackConversationHistoryFormatter
from agent.services.slack.formatter.slack_conversation_replies_formatter import SlackConversationRepliesFormatter
from agent.services.slack.formatter.slack_channel_members_formatter import SlackChannelMembersFormatter


class AgentslackCustomToolService:
    ADD_REACTION_EMOJI = '-1::skin-tone-4'
    CHANNEL_GATE_EXEMPT_TOOLS = {'add_reaction'}

    def __init__(self, team):
        self.team = team
        self._handlers = {
            'search_whitelisted_channels': self._handle_search,
            'conversations_history': self._handle_conversations_history,
            'conversations_replies': self._handle_conversations_replies,
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
        if (
            channel is not None
            and event.name not in self.CHANNEL_GATE_EXEMPT_TOOLS
            and channel not in channel_mapping
        ):
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

        result = SlackChannelSearchAssistantService(self.team.slack_user_token).search(
            query=event.input.get('query'),
            channel_ids=channel_ids,
            users_from=event.input.get('users_from'),
            include_bots=event.input.get('include_bots', False),
            include_deleted_users=event.input.get('include_deleted_users', False),
            before=event.input.get('before'),
            after=event.input.get('after'),
            include_context_messages=event.input.get('include_context_messages'),
            context_channel_id=context_channel_id,
            cursor=event.input.get('cursor'),
            sort_dir=event.input.get('sort_dir'),
            term_clauses=event.input.get('term_clauses'),
            disable_semantic_search=event.input.get('disable_semantic_search', False),
            channel_mapping=channel_mapping
        )
        formated_text = SlackSearchResultFormatter().format(result)
        return self._reply(event, result, formated_text, out_of_scope)

    def _handle_conversations_history(self, event, channel_mapping):
        result = SlackConversationHistoryService().history(
            channel=event.input.get('channel'),
            include_activity_messages=event.input.get('include_activity_messages', False),
            cursor=event.input.get('cursor'),
            oldest=event.input.get('oldest'),
            latest=event.input.get('latest'),
            slack_user_token=self.team.slack_user_token,
        )
        formated_text = SlackConversationHistoryFormatter().format(result)
        return self._reply(event, result, formated_text)

    def _handle_conversations_replies(self, event, channel_mapping):
        result = SlackConversationRepliesService().replies(
            channel=event.input.get('channel'),
            thread_ts=event.input.get('thread_ts'),
            include_activity_messages=event.input.get('include_activity_messages', False),
            cursor=event.input.get('cursor'),
            oldest=event.input.get('oldest'),
            latest=event.input.get('latest'),
            slack_user_token=self.team.slack_user_token,
        )
        formated_text = SlackConversationRepliesFormatter().format(result)
        return self._reply(event, result, formated_text)

    def _handle_list_conversation_members(self, event, channel_mapping):
        result = SlackChannelMembersService().members(event.input.get('channel'), self.team.slack_user_token)
        formated_text = SlackChannelMembersFormatter().format(result)
        return self._reply(event, result, formated_text)

    def _handle_get_user_profile(self, event, channel_mapping):
        result = SlackUserProfileService().get_user(event.input.get('user_id'), self.team.slack_user_token)
        return self._reply(event, result)

    def _handle_list_channels(self, event, channel_mapping):
        mapping = SlackChannelService()._fetch_id_to_name(self.team.slack_user_token)
        result = [{'channel_id': channel_id, 'name': name} for channel_id, name in mapping.items()]
        return self._reply(event, result)

    def _handle_list_usergroups(self, event, channel_mapping):
        result = SlackUserGroupsService().list_with_members(self.team.slack_user_token)
        return self._reply(event, result)

    def _handle_add_reaction(self, event, channel_mapping):
        result = SlackReactionsService().add_reaction(
            channel_id=event.input.get('channel'),
            timestamp=event.input.get('timestamp'),
            emoji_name=self.ADD_REACTION_EMOJI,
            slack_user_token=self.team.slack_user_token,
        )
        return self._reply(event, result)

    def _reply(self, event, result, formated_text=None, out_of_scope=None):
        if isinstance(result, dict) and result.get('error'):
            return self._result(event, result['error'], is_error=True)
        if isinstance(result, list) and not result:
            return self._result(event, 'No results found.')
        if formated_text is None:
            formated_text = json.dumps(result, indent=2, default=str)
        if out_of_scope:
            formated_text += f"\n\nNote: these channel_ids were not whitelisted and were excluded from the search: {', '.join(out_of_scope)}"
        return self._result(event, formated_text)

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
