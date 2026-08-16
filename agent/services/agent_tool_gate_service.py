"""Decides whether an agent's MCP tool call is allowed to run, before it executes.

Asana no longer runs as an MCP server — its tools moved to custom tools
(AgentCustomToolService), which enforce constants.py's workspace/project whitelist
themselves via AsanaGateService/AsanaScopeService before ever calling Asana. This gate
only has Slack MCP calls left to check.
"""

from constants import WHITELISTED_CHANNELS
from agent.services.slack_channel_resolver_service import SlackChannelResolverService

# Slack MCP tools whose input carries a channel_id — these get checked against
# WHITELISTED_CHANNELS below. Every other enabled Slack tool (users_search,
# channels_list, channels_me, usergroups_list, saved_list,
# conversations_unreads, ...) has no channel dimension in its input at all, so
# there is nothing here to check — event.input.get('channel_id') on one of
# those would always come back None, and None is never in WHITELISTED_CHANNELS,
# which used to deny every single call to them regardless of agent.yaml's
# enabled: true. Those tools are controlled by agent.yaml's enabled/disabled
# flags instead, not by this per-channel gate.
CHANNEL_SCOPED_SLACK_TOOLS = frozenset({
    'conversations_history',
    'conversations_replies',
    'conversations_mark',
    'conversations_leave',
    'conversations_join',
    'reactions_add',
    'reactions_remove',
    'conversations_search_messages',
})


class AgentToolGateService:

    def __init__(self):
        self.channel_resolver = SlackChannelResolverService()

    def handle_mcp_tool_use(self, event):
        if event.mcp_server_name == 'slack':
            if event.name in CHANNEL_SCOPED_SLACK_TOOLS:
                raw_channel_id = event.input.get('channel_id')
                channel_id = self.channel_resolver.resolve(raw_channel_id)
                if channel_id not in WHITELISTED_CHANNELS:
                    return {
                        "type": "user.tool_confirmation",
                        "tool_use_id": event.id,
                        "result": "deny",
                        "deny_message": f"Channel {raw_channel_id} is not whitelisted. see the whitelisted channel mentioned",
                    }
        return {
            "type": "user.tool_confirmation",
            "tool_use_id": event.id,
            "result": "allow",
        }


__all__ = ['AgentToolGateService']
