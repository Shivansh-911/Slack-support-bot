"""Backs the `asana_search_tasks` custom tool — the premium advanced-search analog,
`GET /workspaces/{workspace_gid}/tasks/search`.

Requires a whitelisted workspace_gid. This endpoint has no per-request project
restriction of its own, so `projects.any` is always forced to
WHITELISTED_ASANA_PROJECTS — narrowed further by an explicit `projects_any` argument if
one is given and it doesn't name anything outside the whitelist. Premium-only and
capped at 100 unstable-ordered results on Asana's side; prefer
`asana_get_tasks_for_project` for exhaustive, paginated listing on free plans.
"""

from constants import WHITELISTED_ASANA_PROJECTS
from agent.exceptions import AsanaApiError
from agent.services.asana.asana_api_client_service import AsanaApiClientService
from agent.services.asana.asana_gate_service import AsanaGateService


class AsanaSearchTasksService:
    FIELDS = 'name,assignee.name,completed,due_on,permalink_url'

    def __init__(self):
        self.client = AsanaApiClientService()
        self.gate = AsanaGateService()

    def search_tasks(
        self,
        workspace_gid,
        text=None,
        assignee_any=None,
        completed=None,
        projects_any=None,
        sort_by=None,
        sort_ascending=None,
        opt_fields=None,
    ):
        if not self.gate.is_workspace_allowed(workspace_gid):
            return {'error': f'Workspace {workspace_gid} is not whitelisted.'}
        scoped_projects = self._scoped_projects(projects_any)
        if not scoped_projects:
            return {'error': 'projects_any names no project on the whitelist.'}
        params = {
            'projects.any': ','.join(scoped_projects),
            'opt_fields': opt_fields or self.FIELDS,
        }
        if text:
            params['text'] = text
        if assignee_any:
            params['assignee.any'] = assignee_any
        if completed is not None:
            params['completed'] = 'true' if completed else 'false'
        if sort_by:
            params['sort_by'] = sort_by
        if sort_ascending is not None:
            params['sort_ascending'] = 'true' if sort_ascending else 'false'
        try:
            return self.client.get(f'/workspaces/{workspace_gid}/tasks/search', params)
        except AsanaApiError as error:
            return {'error': str(error)}

    def _scoped_projects(self, projects_any):
        if not projects_any:
            return list(WHITELISTED_ASANA_PROJECTS)
        return [gid for gid in projects_any if gid in WHITELISTED_ASANA_PROJECTS]


__all__ = ['AsanaSearchTasksService']
