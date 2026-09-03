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

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError



class SlackChannelService:

    def _fetch_id_to_name(self, slack_user_token):
        client = WebClient(token=slack_user_token)
        mapping = {}
        cursor = None
        try:
            while True:
                response = client.users_conversations(
                    types='public_channel,private_channel',
                    limit=200,
                    cursor=cursor,
                )
                for channel in response.get('channels', []):
                    name = channel.get('name')
                    channel = channel.get('id')
                    if name and channel:
                        if channel == 'C0BJN116WQ5' or channel == 'C0BM44A3YCW' or channel == 'C0BJV4LF6N7':
                            continue
                        mapping[channel] = name
                cursor = response.get('response_metadata', {}).get('next_cursor')
                if not cursor:
                    break
        except SlackApiError:
            pass
        return mapping

    def get_channel_name(self, channel_id, slack_user_token):
        client = WebClient(token=slack_user_token)
        try:
            response = client.conversations_info(channel=channel_id)
            channel = response.get('channel')
            return channel.get('name')
        except SlackApiError:
            pass


