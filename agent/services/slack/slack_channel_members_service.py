"""Wraps Slack's `conversations.members` — the member user ID list for a
single conversation. No name resolution here — pair with
SlackUserProfileService to turn an ID into a profile.
"""

from django.conf import settings
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


class SlackChannelMembersService:

    def members(self, channel_id):
        if not channel_id:
            return {'error': 'channel_id is required.'}
        client = WebClient(token=settings.SLACK_USER_TOKEN)
        member_ids = []
        cursor = None
        try:
            while True:
                response = client.conversations_members(channel=channel_id, cursor=cursor, limit=200)
                member_ids.extend(response.get('members', []))
                cursor = response.get('response_metadata', {}).get('next_cursor')
                if not cursor:
                    break
        except SlackApiError as error:
            return {'error': f'Slack request failed: {error}'}
        return member_ids


__all__ = ['SlackChannelMembersService']
