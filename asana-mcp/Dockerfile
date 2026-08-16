# roychri/mcp-server-asana speaks MCP over stdio only — no HTTP transport and no
# Dockerfile of its own. supergateway (supercorp-ai/supergateway) wraps it to expose it
# over HTTP.
#
# Originally bridged to the legacy two-endpoint SSE transport (--ssePath/--messagePath),
# matching korotovsky/slack-mcp-server's shape. Dropped that after Railway's access logs
# showed a recurring collision: some periodic prober (most likely Railway's own health
# check — supergateway itself reports "Health endpoints: (none)") was opening its own
# long-lived `GET /sse` every ~5-9 minutes, and that transport can only hold one active
# SSE session against the single stdio child at a time — so a real client's own `GET /sse`
# landing while the prober's connection was still open 502'd. Streamable HTTP (below) has
# no persistent per-session connection to collide over — every request is self-contained
# — and is also what CMA's own docs describe as the primary transport for `type: url`
# mcp_servers (the legacy-SSE choice for Slack was an unconfirmed gamble that happened to
# work; this is the first case where it visibly didn't).
#
# READ_ONLY_MODE=true is mcp-server-asana's own switch — it stops every create/update/
# delete tool from ever being registered, so there's nothing to disable on the MCP side.
# cma/agent.yaml still lists the write tools with enabled: false for the audit trail, but
# this env var (set as a Railway service variable, not baked in here) is the actual
# enforcement.
FROM node:20-slim

RUN npm install -g supergateway@3.4.3 @roychri/mcp-server-asana@1.8.0

# PORT is only populated at container start (Railway injects it at runtime, not build
# time), so this has to be shell form, not exec form — an exec form CMD (["supergateway",
# ...]) would pass the literal string "$PORT" instead of its value. --baseUrl is SSE-mode
# only and doesn't apply here, so RAILWAY_PUBLIC_DOMAIN is no longer needed at all.
# ASANA_ACCESS_TOKEN and READ_ONLY_MODE are inherited from this process's env into the
# spawned `mcp-server-asana` child by Node's default child_process behavior — nothing to
# wire up explicitly. Stateless mode: no session to collide over, matching the fix above.
CMD sh -c 'supergateway \
  --stdio "mcp-server-asana" \
  --port "$PORT" \
  --outputTransport streamableHttp \
  --streamableHttpPath /mcp'
