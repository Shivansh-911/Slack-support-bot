"""Backs the `asana_list_workspaces` custom tool.

Asana's `/workspaces` endpoint lists every workspace the access token can see, with no
scoping parameter of its own — returning it unfiltered would leak the names of
workspaces outside constants.py's whitelist, the same reason Slack's `channels_list`
MCP tool is kept out of this agent entirely. Filtering the result down to
WHITELISTED_ASANA_WORKSPACES here is what makes it safe to expose as a tool at all.
"""

from agent.exceptions import AsanaApiError
from agent.services.asana.asana_api_client_service import AsanaApiClientService
from agent.services.asana.asana_gate_service import AsanaGateService


class AsanaListWorkspacesService:

    def __init__(self):
        self.client = AsanaApiClientService()
        self.gate = AsanaGateService()

    def list_workspaces(self):
        try:
            workspaces = self.client.get('/workspaces', {'opt_fields': 'name,is_organization'})
        except AsanaApiError as error:
            return {'error': str(error)}
        return [w for w in workspaces if self.gate.is_workspace_allowed(w.get('gid'))]


__all__ = ['AsanaListWorkspacesService']
