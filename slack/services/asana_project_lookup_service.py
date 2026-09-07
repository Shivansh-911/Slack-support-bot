"""Resolves Asana project gids to their names via the Asana API, so a
Teams row can store each whitelisted project's gid and name together.
"""

from agent.services.asana.asana_api_client_service import AsanaApiClientService


class AsanaProjectLookupService:

    def __init__(self):
        self.client = AsanaApiClientService()

    def resolve(self, project_gids):
        return [self._resolve_one(gid) for gid in project_gids]

    def _resolve_one(self, gid):
        project = self.client.get(f'/projects/{gid}', {'opt_fields': 'name'})
        return {'gid': gid, 'name': project.get('name', '')}


__all__ = ['AsanaProjectLookupService']
