"""Provides database query operations for Teams records."""

from django.db import models


class TeamsManager(models.Manager):

    def get_team_ids(self):
        return list(self.values_list('slack_user_id', flat=True))

    def fetch_team(self, slack_user_id):
        return self.filter(slack_user_id=slack_user_id).first()

    def fetch_team_by_name(self, name):
        return self.filter(name=name).first()

    def upsert(self, name, **fields):
        team, _ = self.update_or_create(name=name, defaults=fields)
        return team


__all__ = ['TeamsManager']
