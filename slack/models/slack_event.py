"""Represents a single Slack Events API payload received via the webhook endpoint."""

from django.db import models

from slack.managers import SlackEventManager


class SlackEvent(models.Model):
    event_id = models.CharField(max_length=64, unique=True, null=True, blank=True)
    team_id = models.CharField(max_length=32, blank=True, default='')
    event_type = models.CharField(max_length=64, blank=True, default='')
    payload = models.JSONField(default=dict)
    received_at = models.DateTimeField(auto_now_add=True)

    objects = SlackEventManager()

    class Meta:
        ordering = ['-received_at']

    def __str__(self):
        return f'{self.event_type} ({self.event_id})'


__all__ = ['SlackEvent']
