"""Read-only Asana custom tools — one class per file, modeled on roychri/mcp-server-asana's
tool set, but executed by Django (agent.custom_tool_use) rather than run as an MCP server.

Every tool in this package enforces constants.py's WHITELISTED_ASANA_WORKSPACES /
WHITELISTED_ASANA_PROJECTS before calling Asana, via AsanaGateService (direct
workspace/project gid checks) and AsanaScopeService (resolving a tag/section/task gid to
its governing workspace/project first). See AgentCustomToolService for how these are
dispatched.
"""
