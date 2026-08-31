"""Runs a Slack `assistant.search.context` search by free-text query.

Mirrors that endpoint's parameters (https://docs.slack.dev/reference/methods/assistant.search.context)
parameter-for-parameter, forwarding every optional one Slack accepts.
content_types is always forced to `messages` regardless of what's passed in:
`files`/`channels` results carry no channel_id field, which matters once
channel scoping is reintroduced here.

channel_ids arrives here already filtered to the caller's whitelist —
AgentslackCustomToolService validates each entry against channel_mapping
before this is ever called — and is used to build an `in:<#channel>`
scoped query. exclude_channel_ids is accepted but currently a no-op —
that scoping is being reworked elsewhere and isn't wired back in yet.

users_from is a list of Slack user IDs (already resolved by the caller,
never a raw name) turned into ANDed `from:<@user_id>` clauses — a user
mention, not the `in:<#channel_id>` channel-mention syntax channel_ids
uses.
"""

from django.conf import settings
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


class SlackChannelSearchAssistantService:
    MAX_RESULTS = 5
    CONTENT_TYPES = ["messages"]

    def __init__(self):
        self.client = WebClient(token=settings.SLACK_USER_TOKEN)

    def search(
        self,
            query,
            channel_ids,
            # exclude_channel_ids,
            # action_token,
            users_from,
            include_bots,
            include_deleted_users,
            before,
            after,
            include_context_messages,
            context_channel_id,
            cursor,
            # sort,
            sort_dir,
            # include_message_blocks,
            # highlight,
            term_clauses,
            # modifiers,
            # include_archived_channels,
            disable_semantic_search,
            channel_mapping
    ):

        

        params = {
            "query": self._scoped_query(query, channel_mapping, channel_ids, users_from),
            "content_types": self.CONTENT_TYPES,
            "channel_types": [
                "public_channel",
                "private_channel",
            ],
            "limit": self.MAX_RESULTS,
        }

        optional_params = {
            # "action_token": action_token,
            "include_bots": include_bots,
            "include_deleted_users": include_deleted_users,
            "before": before,
            "after": after,
            "include_context_messages": include_context_messages,
            "context_channel_id": context_channel_id,
            "cursor": cursor,
            "sort": 'score',
            "sort_dir": sort_dir,
            # "include_message_blocks": include_message_blocks,
            # "highlight": highlight,
            "term_clauses": term_clauses,
            # "modifiers": modifiers,
            # "include_archived_channels": include_archived_channels,
            "disable_semantic_search": disable_semantic_search,
        }

        params.update({
            key: value
            for key, value in optional_params.items()
            if value is not None
        })

        try:
            response = self.client.api_call(
                "assistant.search.context",
                json=params,
            )

        except SlackApiError as error:
            return {
                "error": error.response.get("error", str(error))
            }

        # api_call returns a SlackResponse, not a plain dict — it isn't
        # JSON-serializable, so passing it straight through makes the
        # caller's json.dumps(..., default=str) fall back to
        # SlackResponse.__str__ (i.e. Python's str(dict) repr: single
        # quotes, True/False, backslash-escaped newlines) wrapped inside a
        # JSON string. That double-encoded, non-standard blob is far
        # harder for the model to parse reliably than real JSON. Return
        # the plain dict so the caller emits proper JSON instead.
        return response.data

    def _scoped_query(self, query, channel_mapping, channel_ids, users_from):
        user_query = ''
        if users_from:
            user_query = ' '.join(f'from:<@{user_id}>' for user_id in users_from)
        if channel_ids:
            channel_query = self.resolve_search_channels(channel_ids)
        # elif exclude_channel_ids:
        #     scoped_mapping = {
        #         channel_id: name
        #         for channel_id, name in (channel_mapping or {}).items()
        #         if channel_id not in exclude_channel_ids
        #     }
        #     channel_query = self.resolve_search_channels(scoped_mapping)
        else:
            channel_query = self.resolve_search_channels(channel_mapping)
        return f'{query} {user_query} {channel_query}'.strip()

    def resolve_search_channels(self, channel_mapping):
        if not channel_mapping:
            return ''
        return ' OR '.join(f'in:<#{channel_id}>' for channel_id in channel_mapping)


__all__ = ["SlackChannelSearchAssistantService"]
