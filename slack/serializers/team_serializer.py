"""Validates and creates a Teams row via the team-management API.

`slack_user_token` is write-only — this API has no fetch/list endpoint by
design, but a create response echoing the token back would still leak it
into logs, browser history, or a client that stores responses.
"""

from rest_framework import serializers

from slack.models.teams import Teams


class TeamSerializer(serializers.ModelSerializer):
    slack_user_token = serializers.CharField(write_only=True)

    class Meta:
        model = Teams
        fields = [
            'id',
            'name',
            'slack_user_id',
            'slack_user_token',
            'cma_memory_id',
            'cma_instructions_memory_id',
            'asana_workspace_gid',
            'asana_project_gids',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


__all__ = ['TeamSerializer']
