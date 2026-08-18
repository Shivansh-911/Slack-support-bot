"""Wraps Slack's `users.info` — a single user's profile by user_id."""

from django.conf import settings
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


class SlackUserProfileService:

    def get_user(self, user_id):
        if not user_id:
            return {'error': 'user_id is required.'}
        client = WebClient(token=settings.SLACK_BOT_TOKEN)
        try:
            response = client.users_info(user=user_id)
        except SlackApiError as error:
            return {'error': f'Slack request failed: {error}'}
        member = response.get('user', {}) or {}
        profile = member.get('profile', {}) or {}
        return {
            'user_id': member.get('id'),
            'name': member.get('name') or '',
            'real_name': member.get('real_name') or '',
            'display_name': profile.get('display_name') or '',
            'email': profile.get('email') or '',
            'is_bot': member.get('is_bot', False),
        }


__all__ = ['SlackUserProfileService']
