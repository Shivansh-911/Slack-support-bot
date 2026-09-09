"""Backs the `asana_get_user` custom tool. A user carries no project or workspace gid
of its own on the input, only workspace memberships once fetched, so AsanaScopeService
resolves and checks those before this fetches the user's full record.
"""

from agent.exceptions import AsanaApiError
from agent.services.asana.asana_api_client_service import AsanaApiClientService
from agent.services.asana.asana_scope_service import AsanaScopeService


class AsanaGetUserService:
    FIELDS = 'name,email,workspaces.name'

    def __init__(self, team):
        self.client = AsanaApiClientService()
        self.scope = AsanaScopeService(team)

    def get_user(self, user_gid):
        if not self.scope.is_user_allowed(user_gid):
            return {'error': f'User {user_gid} does not resolve to a whitelisted workspace.'}
        try:
            return self.client.get(f'/users/{user_gid}', {'opt_fields': self.FIELDS})
        except AsanaApiError as error:
            return {'error': str(error)}


__all__ = ['AsanaGetUserService']
