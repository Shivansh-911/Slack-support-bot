"""Checks a workspace or project gid against a team's Asana whitelist.

This is the single membership check every tool in this package ultimately runs
through — directly for tools that already carry a workspace/project gid, or via
AsanaScopeService for tools that only carry a tag/section/task gid and need one
resolved first. The whitelist itself now lives on the team's own row
(Teams.asana_workspace_gid / Teams.asana_project_gids), not a shared
constants.py, so a check for one team can never leak scope from another.
"""


class AsanaGateService:

    def __init__(self, team):
        self.team = team

    def is_workspace_allowed(self, workspace_gid):
        return bool(workspace_gid) and workspace_gid == self.team.asana_workspace_gid

    def is_project_allowed(self, project_gid):
        return bool(project_gid) and project_gid in self.team.asana_project_gids


__all__ = ['AsanaGateService']
