"""Wraps Slack's `conversations.members` — the member ID list for a single
channel — restricted to constants.WHITELISTED_CHANNELS the same way every
other channel-scoped call in this codebase is. Accepts a channel ID or name
(resolved via SlackChannelResolverService) so callers don't need to
pre-resolve.

Member IDs only: this endpoint carries no name data at all — that's why
SlackUserDirectoryService, not this, is what actually searches by name. This
service exists purely to answer "is this specific person currently in this
specific channel," used both as its own tool (`list_channel_members`) and as a
disambiguation signal inside SlackUserSearchAssistantService.

Membership is cached per channel ID for the process lifetime, same trade-off
as SlackChannelResolverService's name cache: a join/leave mid-process won't be
reflected until the next restart.
"""

from django.conf import settings
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from constants import WHITELISTED_CHANNELS
from agent.services.slack_channel_resolver_service import SlackChannelResolverService


class SlackChannelMembersService:
    _members_cache = {}  # channel_id -> set of member user IDs, process-lifetime

    def __init__(self):
        self.channel_resolver = SlackChannelResolverService()

    def members(self, channel_ref):
        """Returns the set of member user IDs for channel_ref (an ID or
        name), or a dict with an 'error' key if it's not whitelisted or
        can't be resolved."""
        channel_id = self.channel_resolver.resolve(channel_ref)
        if channel_id not in WHITELISTED_CHANNELS:
            return {'error': f'Channel {channel_ref} is not whitelisted.'}
        if channel_id not in SlackChannelMembersService._members_cache:
            SlackChannelMembersService._members_cache[channel_id] = self._fetch_members(channel_id)
        return SlackChannelMembersService._members_cache[channel_id]

    def _fetch_members(self, channel_id):
        client = WebClient(token=settings.SLACK_USER_TOKEN)
        member_ids = set()
        cursor = None
        try:
            while True:
                response = client.conversations_members(channel=channel_id, cursor=cursor, limit=200)
                member_ids.update(response.get('members', []))
                cursor = response.get('response_metadata', {}).get('next_cursor')
                if not cursor:
                    break
        except SlackApiError:
            # Fail closed on partial data, same rationale as elsewhere in this
            # codebase: whatever was gathered before the error still gets
            # cached and used.
            pass
        return member_ids


__all__ = ['SlackChannelMembersService']
