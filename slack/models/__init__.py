"""Exposes the slack app's model classes."""

from slack.models.slack_event import SlackEvent
from slack.models.teams import Teams

__all__ = ['SlackEvent', 'Teams']
