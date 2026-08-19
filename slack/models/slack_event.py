"""Represents a single Slack Events API payload received via the webhook endpoint."""

from django.db import models

from slack.managers import SlackEventManager


class SlackEvent(models.Model):
    event_id = models.CharField(max_length=64, unique=True)
    team_id = models.CharField(max_length=32)
    event_type = models.CharField(max_length=64)
    payload = models.JSONField(default=dict)
    received_at = models.DateTimeField(auto_now_add=True)

    objects = SlackEventManager()
