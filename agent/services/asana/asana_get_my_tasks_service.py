"""Backs the `asana_get_my_tasks` custom tool.

Asana has no direct "my tasks" endpoint — this follows the real API shape: resolve the
caller's per-workspace user task list (`GET /users/me/user_task_list`), then list that
list's tasks. Requires a whitelisted workspace_gid, checked before either call is made.
"""

from agent.exceptions import AsanaApiError
from agent.services.asana.asana_api_client_service import AsanaApiClientService
from agent.services.asana.asana_gate_service import AsanaGateService


class AsanaGetMyTasksService:
    FIELDS = 'name,completed,due_on,permalink_url'

    def __init__(self, team):
        self.client = AsanaApiClientService()
        self.gate = AsanaGateService(team)

    def get_my_tasks(self, workspace_gid, completed_since=None, opt_fields=None, limit=100):
        if not self.gate.is_workspace_allowed(workspace_gid):
            return {'error': f'Workspace {workspace_gid} is not whitelisted.'}
        try:
            user_task_list = self.client.get(
                '/users/me/user_task_list', {'workspace': workspace_gid, 'opt_fields': 'gid'}
            )
            params = {'opt_fields': opt_fields or self.FIELDS}
            if completed_since:
                params['completed_since'] = completed_since
            return self.client.get_paginated(
                f"/user_task_lists/{user_task_list['gid']}/tasks", params, limit
            )
        except AsanaApiError as error:
            return {'error': str(error)}


__all__ = ['AsanaGetMyTasksService']
