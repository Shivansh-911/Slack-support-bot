"""Shared constants for the Slack CMA backend.
WHITELISTED_ASANA_WORKSPACES / WHITELISTED_ASANA_PROJECTS are the equivalent
single source of truth for Asana scope, read by agent/services/asana/'s
AsanaGateService (direct workspace/project gid checks) and AsanaScopeService
(resolving a tag/section/task gid to its governing workspace/project first).
gids, not names — Asana's API identifies everything by gid.
"""

WHITELISTED_ASANA_WORKSPACES = {
    "1203355867603831",
}

WHITELISTED_ASANA_PROJECTS = {
    # "1211120697187537",
    # "1216649926845343",
    # "1213394818349982",
    "1211134942672045"
}
