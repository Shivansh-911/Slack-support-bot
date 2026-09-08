"""Resolves an Asana tag, section, task, or user gid to the workspace/project gid that
actually governs its whitelist membership, then checks it via AsanaGateService.

A tag only carries a workspace, a section only carries a project, a task carries
neither on its compact `/tasks/{gid}` record, and a user carries a list of workspace
memberships instead of a single one — each is resolved with one extra read before the
whitelist check, failing closed if that lookup itself errors.
"""

from agent.exceptions import AsanaApiError
from agent.services.asana.asana_api_client_service import AsanaApiClientService
from agent.services.asana.asana_gate_service import AsanaGateService


class AsanaScopeService:

    def __init__(self, team):
        self.client = AsanaApiClientService()
        self.gate = AsanaGateService(team)

    def is_tag_allowed(self, tag_gid):
        try:
            tag = self.client.get(f'/tags/{tag_gid}', {'opt_fields': 'workspace'})
        except AsanaApiError:
            return False
        return self.gate.is_workspace_allowed((tag.get('workspace') or {}).get('gid'))

    def is_section_allowed(self, section_gid):
        try:
            section = self.client.get(f'/sections/{section_gid}', {'opt_fields': 'project'})
        except AsanaApiError:
            return False
        return self.gate.is_project_allowed((section.get('project') or {}).get('gid'))

    def is_task_allowed(self, task_gid):
        try:
            task = self.client.get(f'/tasks/{task_gid}', {'opt_fields': 'projects,workspace'})
        except AsanaApiError:
            return False
        return self._task_payload_in_scope(task)

    def allowed_task_gids(self, task_gids):
        return [task_gid for task_gid in task_gids if self.is_task_allowed(task_gid)]

    def is_user_allowed(self, user_gid):
        try:
            user = self.client.get(f'/users/{user_gid}', {'opt_fields': 'workspaces'})
        except AsanaApiError:
            return False
        workspace_gids = [workspace.get('gid') for workspace in user.get('workspaces') or []]
        return any(self.gate.is_workspace_allowed(gid) for gid in workspace_gids)

    def _task_payload_in_scope(self, task):
        project_gids = [project.get('gid') for project in task.get('projects') or []]
        if any(self.gate.is_project_allowed(gid) for gid in project_gids):
            return True
        return self.gate.is_workspace_allowed((task.get('workspace') or {}).get('gid'))


__all__ = ['AsanaScopeService']
