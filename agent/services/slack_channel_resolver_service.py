"""Resolves a Slack channel reference — a real channel ID, or a bare/`#`-prefixed
name — to its canonical channel ID, without keeping any static name-to-ID
mapping in the codebase. Channel names drift (renames); IDs don't, so
constants.WHITELISTED_CHANNELS stays ID-only and this is the only place a name
ever gets looked up, on demand, against Slack itself.

Anything already shaped like a Slack channel ID (`C`/`G`/`D` followed by
several uppercase alphanumerics) is returned as-is with no API call — this is
the common case, since callers are expected to have already resolved a name
via search results or `channels_list` before reaching here. Anything else is
treated as a name and looked up via `conversations.list`, which has to page
through every channel the bot can see regardless of which one we're after, so
the result is cached for the lifetime of the process rather than re-fetched
per call. That means a channel renamed after this process started won't
resolve under its new name until the next restart — an acceptable trade-off
given how rarely channels are renamed, but worth knowing if a resolution ever
looks stale.

Deliberately not exposed to the agent as a tool: this is called from inside
AgentToolGateService / SlackChannelSearchAssistantService, server-side, so a
name resolves (or fails to) without ever handing the model the full channel
list the way the `channels_list` MCP tool would.
"""

import re

from django.conf import settings
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

_CHANNEL_ID_RE = re.compile(r'^[CGD][A-Z0-9]{7,}$')


class SlackChannelResolverService:
    _name_to_id_cache = None

    def resolve(self, channel_ref):
        """Returns channel_ref's channel ID, or None if it can't be resolved.

        channel_ref may already be an ID (returned unchanged), a bare name, or
        a `#name`/`@name`. Falsy input returns None.
        """
        if not channel_ref:
            return None
        if _CHANNEL_ID_RE.match(channel_ref):
            return channel_ref
        name = channel_ref.lstrip('#').lstrip('@').lower()
        return self._name_to_id().get(name)

    def _name_to_id(self):
        if SlackChannelResolverService._name_to_id_cache is None:
            SlackChannelResolverService._name_to_id_cache = self._fetch_name_to_id()
        return SlackChannelResolverService._name_to_id_cache

    def _fetch_name_to_id(self):
        client = WebClient(token=settings.SLACK_USER_TOKEN)
        mapping = {}
        cursor = None
        try:
            while True:
                response = client.conversations_list(
                    types='public_channel,private_channel',
                    exclude_archived=False,
                    limit=200,
                    cursor=cursor,
                )
                for channel in response.get('channels', []):
                    name = channel.get('name')
                    channel_id = channel.get('id')
                    if name and channel_id:
                        mapping[name.lower()] = channel_id
                cursor = response.get('response_metadata', {}).get('next_cursor')
                if not cursor:
                    break
        except SlackApiError:
            # Fail closed: whatever we'd already gathered still gets cached and
            # used, but we don't retry mid-request — a name that isn't in a
            # partial mapping will fail to resolve and be denied, not silently
            # let through.
            pass
        return mapping


__all__ = ['SlackChannelResolverService']
