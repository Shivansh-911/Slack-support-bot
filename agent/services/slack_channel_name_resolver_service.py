"""Resolves a whitelisted Slack channel ID to its channel name — the inverse
of SlackChannelResolverService's name-to-ID lookup.

Used two ways: server-side, by SlackEventListenerService, to attach the
current channel's name to the context sent with every agent run; and
agent-side, as the `resolve_channel_name` custom tool, for a channel_id the
agent encounters in tool output (e.g. from conversations_history) that isn't
already paired with a name.

Restricted to constants.WHITELISTED_CHANNELS: as an agent-facing tool, this
must not become a way to enumerate channel names outside this agent's
allowlist, so anything else is rejected before Slack is ever called.

Builds its own id-to-name mapping via a paginated `conversations.list` call
against SLACK_USER_TOKEN, cached for the lifetime of the process — same
trade-off as SlackChannelResolverService: a channel renamed after this
process started won't resolve under its new name until the next restart.
"""

from django.conf import settings
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from constants import WHITELISTED_CHANNELS


class SlackChannelNameResolverService:
    _id_to_name_cache = None

    def resolve(self, channel_id):
        """Returns channel_id's channel name, an {'error': ...} dict if it
        isn't whitelisted, or None for falsy input.
        """
        if not channel_id:
            return None
        if channel_id not in WHITELISTED_CHANNELS:
            return {'error': f'Channel {channel_id} is not whitelisted.'}
        return self._id_to_name().get(channel_id, channel_id)

    def _id_to_name(self):
        if SlackChannelNameResolverService._id_to_name_cache is None:
            SlackChannelNameResolverService._id_to_name_cache = self._fetch_id_to_name()
        return SlackChannelNameResolverService._id_to_name_cache

    def _fetch_id_to_name(self):
        client = WebClient(token=settings.SLACK_USER_TOKEN)
        mapping = {}
        cursor = None
        try:
            while True:
                response = client.conversations_list(
                    types='public_channel,private_channel',
                    exclude_archived=False,
                    limit=200,
                    cursor=cursor,
                )
                for channel in response.get('channels', []):
                    name = channel.get('name')
                    channel_id = channel.get('id')
                    if name and channel_id:
                        mapping[channel_id] = name
                cursor = response.get('response_metadata', {}).get('next_cursor')
                if not cursor:
                    break
        except SlackApiError:
            # Fail closed: whatever we'd already gathered still gets cached
            # and used, but we don't retry mid-request — a channel that isn't
            # in a partial mapping just falls back to its raw ID in resolve().
            pass
        return mapping


__all__ = ['SlackChannelNameResolverService']
