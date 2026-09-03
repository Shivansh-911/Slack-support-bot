"""Wraps Slack's `reactions.add` — adds an emoji reaction to a message.

Uses the bot token (`reactions:write` scope), not the user token the other
Slack services in this package read with — reacting is an action taken as
the bot, not a read performed on the user's behalf.
"""

from django.conf import settings
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


class SlackReactionsService:

    def add_reaction(self, channel_id, timestamp, emoji_name, slack_user_token):
        if not channel_id or not timestamp or not emoji_name:
            return {'error': 'channel_id, timestamp, and emoji_name are all required.'}
        client = WebClient(token=slack_user_token)
        try:
            client.reactions_add(channel=channel_id, timestamp=timestamp, name=emoji_name)
        except SlackApiError as error:
            return {'error': f'Slack request failed: {error}'}
        return {'ok': True, 'channel': channel_id, 'timestamp': timestamp, 'emoji_name': emoji_name}


__all__ = ['SlackReactionsService']
