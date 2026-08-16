"""Backs the `asana_get_project_status` custom tool — one status update, by its own gid.

Known enforcement gap, disclosed rather than silently assumed safe: Asana's
`/project_statuses/{gid}` record carries no project or workspace reference of its own,
so there is nothing here to resolve and check the way task/tag/section gids are
resolved elsewhere in this package. Scope is enforced only by provenance — this tool is
only safe to call on a status gid that already came back from a whitelist-checked
`asana_get_project_statuses` call, never on a bare status gid handed in from outside.
The agent-facing tool description says this explicitly; there is no code-level backstop
for this one endpoint.
"""

from agent.exceptions import AsanaApiError
from agent.services.asana.asana_api_client_service import AsanaApiClientService


class AsanaGetProjectStatusService:
    FIELDS = 'text,title,color,created_by.name,created_at'

    def __init__(self):
        self.client = AsanaApiClientService()

    def get_project_status(self, project_status_gid):
        try:
            return self.client.get(f'/project_statuses/{project_status_gid}', {'opt_fields': self.FIELDS})
        except AsanaApiError as error:
            return {'error': str(error)}


__all__ = ['AsanaGetProjectStatusService']
