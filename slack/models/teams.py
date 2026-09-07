"""Represents one internal team: its dedicated Slack seat used to identify
and scope its channels, and its Asana workspace/project whitelist. The
shared Slack bot token/signing secret and the shared Asana PAT stay in
settings — only what's listed here differs per team.

`asana_project_gids` stores each whitelisted project as a `{"gid", "name"}`
pair — the name is resolved from Asana and kept only for display, so
whitelist checks must go through `asana_project_gid_list` rather than
this field directly.

`cma_agent_id` is the Claude Managed Agents agent used to power this
team's sessions — required per team, no global fallback.
"""

from django.db import models

from slack.managers import TeamsManager


class Teams(models.Model):
    name = models.CharField(max_length=64, unique=True)
    slack_user_id = models.CharField(max_length=32, unique=True)
    slack_user_token = models.CharField(max_length=256)
    cma_agent_id = models.CharField(max_length=128)
    cma_memory_id = models.CharField(max_length=128, blank=True, default='')
    cma_instructions_memory_id = models.CharField(max_length=128, blank=True, default='')
    asana_workspace_gid = models.CharField(max_length=32, blank=True, default='')
    asana_project_gids = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = TeamsManager()

    @property
    def asana_project_gid_list(self):
        return [project.get('gid') for project in self.asana_project_gids]
