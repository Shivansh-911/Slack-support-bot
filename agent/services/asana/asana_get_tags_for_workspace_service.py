"""Backs the `asana_get_tags_for_workspace` custom tool. Checked directly against
constants.py's workspace whitelist — a workspace carries its own gid.
"""

from agent.exceptions import AsanaApiError
from agent.services.asana.asana_api_client_service import AsanaApiClientService
from agent.services.asana.asana_gate_service import AsanaGateService


class AsanaGetTagsForWorkspaceService:
    FIELDS = 'name'

    def __init__(self, team):
        self.client = AsanaApiClientService()
        self.gate = AsanaGateService(team)

    def get_tags_for_workspace(self, workspace_gid):
        if not self.gate.is_workspace_allowed(workspace_gid):
            return {'error': f'Workspace {workspace_gid} is not whitelisted.'}
        try:
            return self.client.get(f'/workspaces/{workspace_gid}/tags', {'opt_fields': self.FIELDS})
        except AsanaApiError as error:
            return {'error': str(error)}


__all__ = ['AsanaGetTagsForWorkspaceService']
