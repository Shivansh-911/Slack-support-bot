"""Backs the `asana_get_multiple_tasks_by_gid` custom tool — batch lookup, capped at 25
gids per Asana's own limit for this operation.

Unlike a single-item lookup this checks every gid individually via AsanaScopeService
before fetching it — there is no bulk scope check, so a mixed batch silently returns
only the gids that resolve to the whitelist, with the excluded ones reported by gid
rather than dropped without explanation.
"""

from agent.exceptions import AsanaApiError
from agent.services.asana.asana_api_client_service import AsanaApiClientService
from agent.services.asana.asana_scope_service import AsanaScopeService


class AsanaGetMultipleTasksByGidService:
    MAX_GIDS = 25
    FIELDS = 'name,completed,assignee.name,due_on,permalink_url'

    def __init__(self):
        self.client = AsanaApiClientService()
        self.scope = AsanaScopeService()

    def get_multiple_tasks_by_gid(self, task_gids, opt_fields=None):
        if len(task_gids) > self.MAX_GIDS:
            return {'error': f'At most {self.MAX_GIDS} gids allowed, got {len(task_gids)}.'}
        allowed_gids = set(self.scope.allowed_task_gids(task_gids))
        skipped_gids = [gid for gid in task_gids if gid not in allowed_gids]
        try:
            tasks = [
                self.client.get(f'/tasks/{gid}', {'opt_fields': opt_fields or self.FIELDS})
                for gid in task_gids if gid in allowed_gids
            ]
        except AsanaApiError as error:
            return {'error': str(error)}
        return {'tasks': tasks, 'skipped_not_whitelisted': skipped_gids}


__all__ = ['AsanaGetMultipleTasksByGidService']
