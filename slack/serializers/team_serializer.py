"""Validates and creates a Teams row via the team-management API.

`slack_user_token` is write-only — this API has no fetch/list endpoint by
design, but a create response echoing the token back would still leak it
into logs, browser history, or a client that stores responses.

`asana_project_gids` is input as a flat list of gids; each is resolved to
its project name via AsanaProjectLookupService during validation, so what
gets saved pairs every gid with its name.
"""

from rest_framework import serializers

from agent.exceptions import AsanaApiError
from slack.models.teams import Teams
from slack.services.asana_project_lookup_service import AsanaProjectLookupService


class TeamSerializer(serializers.ModelSerializer):
    slack_user_token = serializers.CharField(write_only=True)

    class Meta:
        model = Teams
        fields = [
            'id',
            'name',
            'slack_user_id',
            'slack_user_token',
            'cma_agent_id',
            'cma_memory_id',
            'cma_instructions_memory_id',
            'asana_workspace_gid',
            'asana_project_gids',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def validate_asana_project_gids(self, value):
        if not all(isinstance(gid, str) for gid in value):
            raise serializers.ValidationError('asana_project_gids must be a list of gid strings.')
        try:
            return AsanaProjectLookupService().resolve(value)
        except AsanaApiError as error:
            raise serializers.ValidationError(str(error))


__all__ = ['TeamSerializer']
