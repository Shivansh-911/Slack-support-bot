"""Represents one internal team: its dedicated Slack seat used to identify
and scope its channels, and its Asana workspace/project whitelist. The
shared Slack bot token/signing secret and the shared Asana PAT stay in
settings — only what's listed here differs per team.
"""

from django.db import models

from slack.managers import TeamsManager


class Teams(models.Model):
    name = models.CharField(max_length=64, unique=True)
    slack_user_id = models.CharField(max_length=32, unique=True)
    slack_user_token = models.CharField(max_length=256)
    cma_memory_id = models.CharField(max_length=128, blank=True, default='')
    cma_instructions_memory_id = models.CharField(max_length=128, blank=True, default='')
    asana_workspace_gid = models.CharField(max_length=32, blank=True, default='')
    asana_project_gids = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = TeamsManager()
