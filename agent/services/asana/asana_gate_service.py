"""Checks a workspace or project gid against constants.py's Asana whitelist.

This is the single membership check every tool in this package ultimately runs
through — directly for tools that already carry a workspace/project gid, or via
AsanaScopeService for tools that only carry a tag/section/task gid and need one
resolved first.
"""

from constants import WHITELISTED_ASANA_PROJECTS, WHITELISTED_ASANA_WORKSPACES


class AsanaGateService:

    def is_workspace_allowed(self, workspace_gid):
        return bool(workspace_gid) and workspace_gid in WHITELISTED_ASANA_WORKSPACES

    def is_project_allowed(self, project_gid):
        return bool(project_gid) and project_gid in WHITELISTED_ASANA_PROJECTS


__all__ = ['AsanaGateService']
