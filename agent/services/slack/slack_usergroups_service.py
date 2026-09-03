"""Wraps Slack's `usergroups.list` and `usergroups.users.list` — every
Slack User Group this token can see, each paired with its member user IDs.

Mirrors SlackChannelMembersService: member IDs come back bare, not names —
pair with SlackUserProfileService for any ID that needs a name.
"""

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


class SlackUserGroupsService:

    def list_with_members(self, slack_user_token):
        client = WebClient(token=slack_user_token)
        try:
            response = client.usergroups_list(include_count=True, include_disabled=False)
        except SlackApiError as error:
            return {'error': f'Slack request failed: {error}'}
        groups = []
        for usergroup in response.get('usergroups', []):
            groups.append({
                'id': usergroup.get('id'),
                'name': usergroup.get('name') or '',
                'handle': usergroup.get('handle') or '',
                'description': usergroup.get('description') or '',
                'user_count': usergroup.get('user_count'),
                'users': self._members(client, usergroup.get('id')),
            })
        return groups

    def _members(self, client, usergroup_id):
        try:
            response = client.usergroups_users_list(usergroup=usergroup_id)
        except SlackApiError:
            return []
        return response.get('users', [])


__all__ = ['SlackUserGroupsService']
