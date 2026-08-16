"""Backs the `asana_search_projects` custom tool — regex name matching over a
workspace's projects.

Requires a whitelisted workspace_gid. Asana has no server-side regex filter for project
names, so this fetches every project in the workspace and filters client-side with
`re.search`, then filters again down to WHITELISTED_ASANA_PROJECTS — the workspace can
hold projects outside that whitelist, and a name match alone must not surface them.
"""

import re

from agent.exceptions import AsanaApiError
from agent.services.asana.asana_api_client_service import AsanaApiClientService
from agent.services.asana.asana_gate_service import AsanaGateService


class AsanaSearchProjectsService:
    FIELDS = 'name,archived'

    def __init__(self):
        self.client = AsanaApiClientService()
        self.gate = AsanaGateService()

    def search_projects(self, workspace_gid, name_pattern, archived=None):
        if not self.gate.is_workspace_allowed(workspace_gid):
            return {'error': f'Workspace {workspace_gid} is not whitelisted.'}
        try:
            pattern = re.compile(name_pattern)
        except re.error as error:
            return {'error': f'Invalid name_pattern: {error}'}
        params = {'workspace': workspace_gid, 'opt_fields': self.FIELDS, 'limit': 100}
        if archived is not None:
            params['archived'] = 'true' if archived else 'false'
        try:
            projects = self.client.get('/projects', params)
        except AsanaApiError as error:
            return {'error': str(error)}
        return [
            project for project in projects
            if pattern.search(project.get('name') or '') and self.gate.is_project_allowed(project.get('gid'))
        ]


__all__ = ['AsanaSearchProjectsService']
