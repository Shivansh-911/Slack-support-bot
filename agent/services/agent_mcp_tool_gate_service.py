"""Decides whether an agent's MCP tool call is allowed to run, before it executes.

Asana no longer runs as an MCP server — its tools moved to custom tools
(AgentCustomToolService), which enforce constants.py's workspace/project whitelist
themselves via AsanaGateService/AsanaScopeService before ever calling Asana. This gate
only has Slack MCP calls left to check.
"""

class AgentMcpToolGateService:

    def handle_mcp_tool_use(self, event, channel_mapping):
        if event.mcp_server_name == 'slack':   

            channel = event.input.get("channel_id")
            if channel is not None and channel not in channel_mapping:
                return {
                    "type": "user.tool_confirmation",
                    "tool_use_id": event.id,
                    "result": "deny",
                    "deny_message": f"{channel} is out of scope"
                }


            return {
                "type": "user.tool_confirmation",
                "tool_use_id": event.id,
                "result": "allow",
            }
        else:
            return 





# return {
#     "type": "user.tool_confirmation",
#     "tool_use_id": event.id,
#     "result": "deny",
#     "deny_message": f"Channel {raw_channel_id} is not whitelisted. see the whitelisted channel mentioned",
# }
