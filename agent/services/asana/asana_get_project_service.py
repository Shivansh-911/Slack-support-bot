"""Backs the `asana_get_project` custom tool. A project carries its own gid up front, so
this checks it directly against constants.py's whitelist — no extra resolution step
needed the way task/tag/section lookups need.
"""

from agent.exceptions import AsanaApiError
from agent.services.asana.asana_api_client_service import AsanaApiClientService
from agent.services.asana.asana_gate_service import AsanaGateService


class AsanaGetProjectService:
    FIELDS = 'name,notes,owner.name,members.name,current_status_update,due_on,archived'

    def __init__(self):
        self.client = AsanaApiClientService()
        self.gate = AsanaGateService()

    def get_project(self, project_gid, opt_fields=None):
        if not self.gate.is_project_allowed(project_gid):
            return {'error': f'Project {project_gid} is not whitelisted.'}
        try:
            return self.client.get(f'/projects/{project_gid}', {'opt_fields': opt_fields or self.FIELDS})
        except AsanaApiError as error:
            return {'error': str(error)}


__all__ = ['AsanaGetProjectService']
