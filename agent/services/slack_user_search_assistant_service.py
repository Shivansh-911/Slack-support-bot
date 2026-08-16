"""Backs two custom tools:

`search_users_directory` — name search over the workspace's user directory
(SlackUserDirectoryService: exact substring first, fuzzy/typo-tolerant
fallback), optionally cross-checked against one whitelisted channel's
membership (SlackChannelMembersService) to help disambiguate when a name
matches more than one person. Channel membership is a disambiguation signal,
not a filter — a genuine match who has since left the channel, or who posted
before joining, is still reported, just annotated `in_channel: false`, so a
real answer never gets silently dropped because of a snapshot of *current*
membership.

`list_channel_members` — the member list for one whitelisted channel, with
real names attached from the same directory cache rather than bare IDs.
"""

from agent.services.slack_user_directory_service import SlackUserDirectoryService
from agent.services.slack_channel_members_service import SlackChannelMembersService


class SlackUserSearchAssistantService:
    MAX_RESULTS = 10

    def __init__(self):
        self.user_directory = SlackUserDirectoryService()
        self.channel_members = SlackChannelMembersService()

    def search(self, query, channel_id=None, limit=MAX_RESULTS):
        if not query:
            return {'error': 'query is required.'}

        matches = self.user_directory.search(query, limit=limit)

        if not channel_id:
            return matches

        members = self.channel_members.members(channel_id)
        if isinstance(members, dict) and members.get('error'):
            return members

        return [
            {**match, 'in_channel': match['user_id'] in members}
            for match in matches
        ]

    def list_channel_members(self, channel_id):
        if not channel_id:
            return {'error': 'channel_id is required.'}

        member_ids = self.channel_members.members(channel_id)
        if isinstance(member_ids, dict) and member_ids.get('error'):
            return member_ids

        resolved = self.user_directory.by_ids(member_ids)
        return [
            {
                'user_id': uid,
                'name': resolved.get(uid, {}).get('name', ''),
                'real_name': resolved.get(uid, {}).get('real_name', ''),
                'display_name': resolved.get(uid, {}).get('display_name', ''),
                'is_bot': resolved.get(uid, {}).get('is_bot', False),
            }
            for uid in sorted(member_ids)
        ]


__all__ = ['SlackUserSearchAssistantService']
