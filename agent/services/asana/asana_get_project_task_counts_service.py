"""Backs the `asana_get_project_task_counts` custom tool. Checked directly against
constants.py's project whitelist — a project carries its own gid.
"""

from agent.exceptions import AsanaApiError
from agent.services.asana.asana_api_client_service import AsanaApiClientService
from agent.services.asana.asana_gate_service import AsanaGateService


class AsanaGetProjectTaskCountsService:
    FIELDS = (
        'num_tasks,num_incomplete_tasks,num_completed_tasks,'
        'num_milestones,num_incomplete_milestones,num_completed_milestones'
    )

    def __init__(self, team):
        self.client = AsanaApiClientService()
        self.gate = AsanaGateService(team)

    def get_project_task_counts(self, project_gid):
        if not self.gate.is_project_allowed(project_gid):
            return {'error': f'Project {project_gid} is not whitelisted.'}
        try:
            return self.client.get(f'/projects/{project_gid}/task_counts', {'opt_fields': self.FIELDS})
        except AsanaApiError as error:
            return {'error': str(error)}


__all__ = ['AsanaGetProjectTaskCountsService']
