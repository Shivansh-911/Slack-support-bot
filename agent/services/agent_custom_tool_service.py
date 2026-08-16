"""Executes agent-invoked custom tools and builds the `user.custom_tool_result` reply.

Custom tools have no MCP-style confirmation step: the agent expects the
client to run the tool itself and answer on the same stream, so this class
dispatches `agent.custom_tool_use` events by tool name and packages whatever
the tool returns into that reply shape, using `event.id` as the
`custom_tool_use_id` the reply must carry.

The 18 read-only Asana tools are handled by AgentAsanaCustomToolService instead of
inline here — see that class's docstring for why it's kept separate.
"""

from agent.services.slack_channel_search_assistant_service import SlackChannelSearchAssistantService
from agent.services.slack_user_search_assistant_service import SlackUserSearchAssistantService
from agent.services.slack_channel_name_resolver_service import SlackChannelNameResolverService
from agent.services.asana.agent_asana_custom_tool_service import AgentAsanaCustomToolService


class AgentCustomToolService:
    SEARCH_TOOL_NAME = 'search_whitelisted_channels'
    SEARCH_USERS_TOOL_NAME = 'search_users_directory'
    LIST_CHANNEL_MEMBERS_TOOL_NAME = 'list_channel_members'
    RESOLVE_CHANNEL_NAME_TOOL_NAME = 'resolve_channel_name'
    OPTIONAL_SEARCH_KEYS = (
        'action_token',
        'include_bots',
        'include_deleted_users',
        'before',
        'after',
        'include_context_messages',
        'cursor',
        'limit',
        'sort',
        'sort_dir',
        'include_message_blocks',
        'highlight',
        'term_clauses',
        'modifiers',
        'include_archived_channels',
        'disable_semantic_search',
    )

    def handle_custom_tool_use(self, event):
        if event.name == self.SEARCH_TOOL_NAME:
            return self._handle_search(event)
        if event.name == self.SEARCH_USERS_TOOL_NAME:
            return self._handle_search_users(event)
        if event.name == self.LIST_CHANNEL_MEMBERS_TOOL_NAME:
            return self._handle_list_channel_members(event)
        if event.name == self.RESOLVE_CHANNEL_NAME_TOOL_NAME:
            return self._handle_resolve_channel_name(event)
        asana_custom_tool_service = AgentAsanaCustomToolService()
        if asana_custom_tool_service.handles(event.name):
            return asana_custom_tool_service.handle_custom_tool_use(event)
        return self._result(event, f'Unknown tool: {event.name}', is_error=True)

    def _handle_search(self, event):
        channel_ids = event.input.get('channel_ids') or None
        exclude_channel_ids = event.input.get('exclude_channel_ids') or None
        query = event.input.get('query', '')
        results = SlackChannelSearchAssistantService().search(
            channel_ids, query, exclude_channel_ids=exclude_channel_ids, **self._optional_search_kwargs(event)
        )
        if isinstance(results, dict) and results.get('error'):
            return self._result(event, results['error'], is_error=True)
        if not results:
            return self._result(event, self._no_results_message(channel_ids, exclude_channel_ids))
        return self._result(event, self._render(results))

    def _optional_search_kwargs(self, event):
        return {key: event.input[key] for key in self.OPTIONAL_SEARCH_KEYS if key in event.input}

    def _handle_search_users(self, event):
        query = event.input.get('query', '')
        channel_id = event.input.get('channel_id') or None
        limit = event.input.get('limit', SlackUserSearchAssistantService.MAX_RESULTS)
        results = SlackUserSearchAssistantService().search(query, channel_id=channel_id, limit=limit)
        if isinstance(results, dict) and results.get('error'):
            return self._result(event, results['error'], is_error=True)
        if not results:
            return self._result(event, f'No users found matching "{query}".')
        return self._result(event, self._render_users(results))

    def _handle_list_channel_members(self, event):
        channel_id = event.input.get('channel_id')
        members = SlackUserSearchAssistantService().list_channel_members(channel_id)
        if isinstance(members, dict) and members.get('error'):
            return self._result(event, members['error'], is_error=True)
        if not members:
            return self._result(event, f'No members found in channel {channel_id}.')
        return self._result(event, self._render_members(members))

    def _handle_resolve_channel_name(self, event):
        channel_id = event.input.get('channel_id')
        result = SlackChannelNameResolverService().resolve(channel_id)
        if isinstance(result, dict) and result.get('error'):
            return self._result(event, result['error'], is_error=True)
        if not result:
            return self._result(event, f'No channel found for {channel_id}.')
        return self._result(event, result)

    def _render_users(self, users):
        lines = []
        for user in users:
            bot_tag = ' [bot]' if user.get('is_bot') else ''
            fuzzy_tag = ' (fuzzy match)' if user.get('match_type') == 'fuzzy' else ''
            in_channel = ''
            if 'in_channel' in user:
                in_channel = ' — in channel' if user['in_channel'] else ' — not currently in that channel'
            lines.append(
                f"[{user['user_id']}] {user['real_name']} (@{user['name']}){bot_tag}{fuzzy_tag}{in_channel}"
            )
        return '\n'.join(lines)

    def _render_members(self, members):
        lines = [
            f"[{member['user_id']}] {member['real_name']} (@{member['name']}){' [bot]' if member['is_bot'] else ''}"
            for member in members
        ]
        return '\n'.join(lines)

    def _no_results_message(self, channel_ids, exclude_channel_ids=None):
        if channel_ids:
            scope = f'in channel(s) {", ".join(channel_ids)}'
        elif exclude_channel_ids:
            scope = f'across the allowed channels except {", ".join(exclude_channel_ids)}'
        else:
            scope = 'across the allowed channels'
        return f'No matching messages found {scope}.'

    def _render(self, results):
        return '\n\n'.join(self._render_result(result) for result in results)

    def _render_result(self, result):
        context = result.get('context') or {}
        lines = [self._render_context_message(m) for m in context.get('before', [])]
        bot_tag = ' [bot]' if result.get('is_bot') else ''
        lines.append(
            f"[{result['channel']}] {result['user']}{bot_tag}: {result['text']} ({result['permalink']})"
        )
        lines.extend(self._render_context_message(m) for m in context.get('after', []))
        return '\n'.join(lines)

    def _render_context_message(self, message):
        return f"    context — {message['user']}: {message['text']}"

    def _result(self, event, text, is_error=False):
        reply = {
            'type': 'user.custom_tool_result',
            'custom_tool_use_id': event.id,
            'content': [{'type': 'text', 'text': text}],
        }
        if is_error:
            reply['is_error'] = True
        return reply


__all__ = ['AgentCustomToolService']
