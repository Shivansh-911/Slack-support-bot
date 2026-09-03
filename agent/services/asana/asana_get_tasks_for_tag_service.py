"""Backs the `asana_get_tasks_for_tag` custom tool. A tag carries no project of its own,
only a workspace, so AsanaScopeService resolves and checks that first.
"""

from agent.exceptions import AsanaApiError
from agent.services.asana.asana_api_client_service import AsanaApiClientService
from agent.services.asana.asana_scope_service import AsanaScopeService


class AsanaGetTasksForTagService:
    FIELDS = 'name,completed,assignee.name,due_on,permalink_url'

    def __init__(self, team):
        self.client = AsanaApiClientService()
        self.scope = AsanaScopeService(team)

    def get_tasks_for_tag(self, tag_gid, opt_fields=None):
        if not self.scope.is_tag_allowed(tag_gid):
            return {'error': f'Tag {tag_gid} does not resolve to a whitelisted workspace.'}
        try:
            return self.client.get(f'/tags/{tag_gid}/tasks', {'opt_fields': opt_fields or self.FIELDS})
        except AsanaApiError as error:
            return {'error': str(error)}


__all__ = ['AsanaGetTasksForTagService']
