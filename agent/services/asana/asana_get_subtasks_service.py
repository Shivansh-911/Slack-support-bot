"""Backs the `asana_get_subtasks` custom tool. `/tasks/{gid}/subtasks` carries no
workspace/project of its own, so AsanaScopeService resolves and checks the parent
task's scope first.
"""

from agent.exceptions import AsanaApiError
from agent.services.asana.asana_api_client_service import AsanaApiClientService
from agent.services.asana.asana_scope_service import AsanaScopeService


class AsanaGetSubtasksService:
    FIELDS = 'name,completed,assignee.name,due_on'

    def __init__(self):
        self.client = AsanaApiClientService()
        self.scope = AsanaScopeService()

    def get_subtasks(self, task_gid):
        if not self.scope.is_task_allowed(task_gid):
            return {'error': f'Task {task_gid} is not in a whitelisted project/workspace.'}
        try:
            return self.client.get(f'/tasks/{task_gid}/subtasks', {'opt_fields': self.FIELDS})
        except AsanaApiError as error:
            return {'error': str(error)}


__all__ = ['AsanaGetSubtasksService']
