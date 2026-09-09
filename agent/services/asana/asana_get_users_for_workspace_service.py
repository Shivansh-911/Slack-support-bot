"""Backs the `asana_get_users_for_workspace` custom tool. Checked directly against
the team's own workspace whitelist — a workspace carries its own gid, the same as
`asana_list_workspaces`.
"""

from agent.exceptions import AsanaApiError
from agent.services.asana.asana_api_client_service import AsanaApiClientService
from agent.services.asana.asana_gate_service import AsanaGateService


class AsanaGetUsersForWorkspaceService:
    FIELDS = 'name,email'

    def __init__(self, team):
        self.client = AsanaApiClientService()
        self.gate = AsanaGateService(team)

    def get_users_for_workspace(self, workspace_gid, opt_fields=None, limit=100):
        if not self.gate.is_workspace_allowed(workspace_gid):
            return {'error': f'Workspace {workspace_gid} is not whitelisted.'}
        params = {'opt_fields': opt_fields or self.FIELDS}
        try:
            return self.client.get_paginated(f'/workspaces/{workspace_gid}/users', params, limit)
        except AsanaApiError as error:
            return {'error': str(error)}


__all__ = ['AsanaGetUsersForWorkspaceService']
