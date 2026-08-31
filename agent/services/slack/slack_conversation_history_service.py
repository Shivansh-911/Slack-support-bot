"""Wraps Slack's `conversations.history` — recent messages from a channel
or DM (https://docs.slack.dev/reference/methods/conversations.history).

The agent-facing schema (see conversations_history in agent.yaml) exposes
only `channel`, `cursor`, `oldest`, and `latest` — no `limit`. Page size is
fixed at PAGE_SIZE on every call instead, so the agent can't ask for more
than that per page and has to paginate with cursor for anything larger.

Slack has no server-side filter for `channel_join`/`channel_leave`-style
activity messages, so `include_activity_messages=False` (the default) is
enforced client-side by dropping any message whose `subtype` is in
ACTIVITY_SUBTYPES.

Returns a plain dict built field-by-field from the SlackResponse, never
the SlackResponse itself — passing that straight through is what caused
the `search_whitelisted_channels` hallucination bug (mangled Python-repr
JSON from a bare `json.dumps` fallback).
"""

from django.conf import settings
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


class SlackConversationHistoryService:
    PAGE_SIZE = 15
    ACTIVITY_SUBTYPES = {
        'channel_join', 'channel_leave', 'channel_topic', 'channel_purpose',
        'channel_name', 'channel_archive', 'channel_unarchive',
        'group_join', 'group_leave', 'group_topic', 'group_purpose',
        'group_name', 'group_archive', 'group_unarchive',
        'pinned_item', 'unpinned_item',
    }

    def history(self, channel, include_activity_messages, cursor, oldest, latest):
        if not channel:
            return {'error': 'channel is required.'}
        client = WebClient(token=settings.SLACK_USER_TOKEN)
        params = {'channel': channel, 'limit': self.PAGE_SIZE}
        if cursor:
            params['cursor'] = cursor
        if oldest is not None:
            params['oldest'] = oldest
        if latest is not None:
            params['latest'] = latest
        try:
            response = client.conversations_history(**params)
        except SlackApiError as error:
            return {'error': f'Slack request failed: {error}'}
        messages = [
            self._format_message(message)
            for message in response.get('messages', [])
            if include_activity_messages or not self._is_activity_message(message)
        ]
        return {
            'messages': messages,
            'has_more': response.get('has_more', False),
            'next_cursor': response.get('response_metadata', {}).get('next_cursor') or '',
        }

    def _is_activity_message(self, message):
        return message.get('subtype') in self.ACTIVITY_SUBTYPES

    def _format_message(self, message):
        formatted = {
            'user': message.get('user') or message.get('bot_id') or '',
            'text': message.get('text', ''),
            'ts': message.get('ts', ''),
        }
        thread_ts = message.get('thread_ts')
        if thread_ts and thread_ts != message.get('ts'):
            formatted['thread_ts'] = thread_ts
        if message.get('reply_count'):
            formatted['reply_count'] = message.get('reply_count')
        if message.get('subtype'):
            formatted['subtype'] = message.get('subtype')
        return formatted


__all__ = ['SlackConversationHistoryService']
