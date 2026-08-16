"""Runs a free-text Slack search scoped to one allowlisted channel.

`search.messages` has no channel-scoping parameter of its own
(https://docs.slack.dev/reference/methods/search.messages/) — Slack scopes a
search to a channel only through the `in:#channel-name` query modifier. The
requested channel is checked against `WHITELISTED_CHANNELS` before any Slack
API call is made, then translated to its name and folded into the query as
that modifier. Every match Slack returns is still re-checked against the
requested channel afterward — that check, not the query text, is the real
boundary, in case the modifier doesn't scope the response as expected.
"""

from django.conf import settings
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from constants import WHITELISTED_CHANNELS


class SlackChannelSearchService:
    MAX_RESULTS = 20

    def search(self, channel_id, query):
        if channel_id not in WHITELISTED_CHANNELS:
            return {'error': f'Channel {channel_id} is not whitelisted for search.'}
        client = WebClient(token=settings.SLACK_USER_TOKEN)
        try:
            response = client.search_messages(
                query=self._scope_to_channel(channel_id, query),
                count=self.MAX_RESULTS,
                sort='timestamp',
                sort_dir='desc',
            )
        except SlackApiError as error:
            return {'error': f'Slack search failed: {error}'}
        matches = response.get('messages', {}).get('matches', [])
        return [self._format(match) for match in matches if self._is_in_channel(match, channel_id)]

    def _scope_to_channel(self, channel_id, query):
        channel_name = WHITELISTED_CHANNELS[channel_id]
        return f'{query} in:#{channel_name}'.strip()

    def _is_in_channel(self, match, channel_id):
        channel = match.get('channel') or {}
        return channel.get('id') == channel_id

    def _format(self, match):
        channel = match.get('channel') or {}
        channel_name = channel.get('name') or WHITELISTED_CHANNELS.get(channel.get('id'), channel.get('id'))
        return {
            'channel': channel_name,
            'user': match.get('username') or match.get('user'),
            'text': match.get('text'),
            'permalink': match.get('permalink'),
            'ts': match.get('ts'),
        }


__all__ = ['SlackChannelSearchService']
