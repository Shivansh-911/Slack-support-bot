"""Backs the `asana_get_task` custom tool.

`/tasks/{gid}` carries no workspace/project field of its own to check up front, so this
always requests `projects.gid`/`workspace.gid` alongside the caller's display fields and
refuses to return anything unless one resolves to constants.py's whitelist — those two
scope-only fields are stripped from the reply unless the caller explicitly asked for
`projects` themselves.
"""

from agent.exceptions import AsanaApiError
from agent.services.asana.asana_api_client_service import AsanaApiClientService
from agent.services.asana.asana_gate_service import AsanaGateService


class AsanaGetTaskService:
    DEFAULT_FIELDS = (
        'name,notes,completed,assignee.name,due_on,projects.name,tags.name,parent.name,'
        'num_subtasks,custom_fields.name,custom_fields.display_value,permalink_url'
    )
    SCOPE_FIELDS = 'projects.gid,workspace.gid'

    def __init__(self, team):
        self.client = AsanaApiClientService()
        self.gate = AsanaGateService(team)

    def get_task(self, task_gid, opt_fields=None):
        requested_fields = opt_fields or self.DEFAULT_FIELDS
        try:
            task = self.client.get(
                f'/tasks/{task_gid}', {'opt_fields': f'{requested_fields},{self.SCOPE_FIELDS}'}
            )
        except AsanaApiError as error:
            return {'error': str(error)}
        if not self._in_scope(task):
            return {'error': f'Task {task_gid} is not in a whitelisted project/workspace.'}
        keep_projects = 'projects' in requested_fields
        return {
            key: value for key, value in task.items()
            if key != 'workspace' and (key != 'projects' or keep_projects)
        }

    def _in_scope(self, task):
        project_gids = [project.get('gid') for project in task.get('projects') or []]
        if any(self.gate.is_project_allowed(gid) for gid in project_gids):
            return True
        return self.gate.is_workspace_allowed((task.get('workspace') or {}).get('gid'))


__all__ = ['AsanaGetTaskService']
