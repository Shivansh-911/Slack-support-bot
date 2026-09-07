"""Backs the `asana_get_tasks_for_project` custom tool — the free-plan-friendly,
fully-paginated alternative to `asana_search_tasks`. Checked directly against
constants.py's project whitelist — a project carries its own gid.
"""

from agent.exceptions import AsanaApiError
from agent.services.asana.asana_api_client_service import AsanaApiClientService
from agent.services.asana.asana_gate_service import AsanaGateService


class AsanaGetTasksForProjectService:
    FIELDS = 'name,completed,assignee.name,due_on,permalink_url'

    def __init__(self, team):
        self.client = AsanaApiClientService()
        self.gate = AsanaGateService(team)

    def get_tasks_for_project(self, project_gid, completed_since=None, opt_fields=None, limit=100):
        if not self.gate.is_project_allowed(project_gid):
            return {'error': f'Project {project_gid} is not whitelisted.'}
        params = {'project': project_gid, 'opt_fields': opt_fields or self.FIELDS}
        if completed_since:
            params['completed_since'] = completed_since
        try:
            return self.client.get_paginated('/tasks', params, limit)
        except AsanaApiError as error:
            return {'error': str(error)}


__all__ = ['AsanaGetTasksForProjectService']
