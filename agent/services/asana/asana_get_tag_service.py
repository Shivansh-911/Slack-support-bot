"""Backs the `asana_get_tag` custom tool. A tag carries no project of its own, only a
workspace, so AsanaScopeService resolves and checks that before this fetches the tag.
"""

from agent.exceptions import AsanaApiError
from agent.services.asana.asana_api_client_service import AsanaApiClientService
from agent.services.asana.asana_scope_service import AsanaScopeService


class AsanaGetTagService:
    FIELDS = 'name,workspace.name'

    def __init__(self):
        self.client = AsanaApiClientService()
        self.scope = AsanaScopeService()

    def get_tag(self, tag_gid):
        if not self.scope.is_tag_allowed(tag_gid):
            return {'error': f'Tag {tag_gid} does not resolve to a whitelisted workspace.'}
        try:
            return self.client.get(f'/tags/{tag_gid}', {'opt_fields': self.FIELDS})
        except AsanaApiError as error:
            return {'error': str(error)}


__all__ = ['AsanaGetTagService']
