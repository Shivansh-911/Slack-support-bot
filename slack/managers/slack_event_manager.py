"""Provides database query and creation operations for Slack event records."""

from django.db import models


class SlackEventManager(models.Manager):
    def has_event_id(self, event_id):
        if not event_id:
            return False
        return self.filter(event_id=event_id).exists()

    def create_from_payload(self, payload):
        event = payload.get('event') or {}
        return self.create(
            event_id=payload.get('event_id'),
            team_id=payload.get('team_id', ''),
            event_type=event.get('type', ''),
            payload=payload,
        )

