"""Runs a Slack assistant.search.context search, scoped to one or more
allowlisted channels when given (`channel_ids`), across every allowlisted
channel except some when told to exclude (`exclude_channel_ids`), or across
every allowlisted channel otherwise.

`channel_ids` and `exclude_channel_ids` are both lists and are mutually
exclusive — passing both is rejected rather than silently preferring one.
Exclusion exists because a caller (the agent) often knows the ID of a channel
it wants *gone* — it just dominated an unscoped search with irrelevant hits —
without knowing the IDs of every other allowlisted channel it would need to
list explicitly instead.

Entries in either list may be a real channel ID or a bare/`#`-prefixed name —
SlackChannelResolverService resolves names to IDs before anything is checked
against the allowlist, so a caller that hasn't (or can't) resolve a name via
`channels_list` first still gets scoped correctly rather than falsely denied.

Channel scoping is expressed as `in:<#channel_id>` modifiers joined with OR
in the query text, one per scoped channel (or per allowed channel, when none
are given). That syntax is unconfirmed for this API (Slack's docs only
document `in:#channel-name`), so every result is still re-checked against the
allowed channel IDs afterward; that check, not the query text, is the real
boundary.

content_types is always forced to `['messages']` regardless of what's
passed in: `files` and `channels` results
(https://docs.slack.dev/reference/methods/assistant.search.context) carry no
channel_id field, so there is no way to re-check them against the allowlist
the way messages are re-checked above — allowing them through would let a
query bypass channel scoping entirely.

The installed slack_sdk version has no `assistant_search_context` wrapper
method (only `assistant_threads_setStatus`/`setTitle`/`setSuggestedPrompts`
exist), so this calls the endpoint directly through `WebClient.api_call`
by its Slack API method name instead, the same way those sibling wrapper
methods do internally. `json=` (rather than `params=`) is used so list/dict
values like `content_types` and `term_clauses` are sent as real JSON rather
than needing manual comma- or JSON-string encoding.
"""

from django.conf import settings
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from constants import WHITELISTED_CHANNELS
from agent.services.slack_channel_resolver_service import SlackChannelResolverService


class SlackChannelSearchAssistantService:
    MAX_RESULTS = 20
    FORCED_CONTENT_TYPES = ['messages']

    def __init__(self):
        self.channel_resolver = SlackChannelResolverService()

    def search(
        self,
        channel_ids,
        query,
        exclude_channel_ids=None,
        action_token=None,
        include_bots=None,
        include_deleted_users=None,
        before=None,
        after=None,
        include_context_messages='true',
        cursor=None,
        limit=MAX_RESULTS,
        sort='score',
        sort_dir='desc',
        include_message_blocks=None,
        highlight=None,
        term_clauses=None,
        modifiers=None,
        include_archived_channels=None,
        disable_semantic_search=None,
    ):
        if channel_ids and exclude_channel_ids:
            return {'error': 'Pass either channel_ids or exclude_channel_ids, not both.'}

        # Resolve names to IDs before validating — a caller may pass a bare
        # name or `#name` instead of a resolved ID; unresolvable refs are left
        # as-is so the error below names what was actually passed.
        channel_ids = self._resolve_all(channel_ids)
        exclude_channel_ids = self._resolve_all(exclude_channel_ids)

        if channel_ids:
            invalid_channel_ids = [cid for cid in channel_ids if cid not in WHITELISTED_CHANNELS]
            if invalid_channel_ids:
                return {'error': f'Channel(s) {invalid_channel_ids} not whitelisted for search.'}
            scoped_channel_ids = channel_ids
        elif exclude_channel_ids:
            invalid_exclusions = [cid for cid in exclude_channel_ids if cid not in WHITELISTED_CHANNELS]
            if invalid_exclusions:
                return {'error': f'Channel(s) {invalid_exclusions} not whitelisted, so they cannot be excluded.'}
            scoped_channel_ids = [cid for cid in WHITELISTED_CHANNELS if cid not in exclude_channel_ids]
            if not scoped_channel_ids:
                return {'error': 'exclude_channel_ids excludes every whitelisted channel — nothing left to search.'}
        else:
            scoped_channel_ids = None

        client = WebClient(token=settings.SLACK_USER_TOKEN)
        params = self._build_params(
            channel_ids=scoped_channel_ids,
            query=query,
            limit=limit,
            action_token=action_token,
            include_bots=include_bots,
            include_deleted_users=include_deleted_users,
            before=before,
            after=after,
            include_context_messages=include_context_messages,
            cursor=cursor,
            sort=sort,
            sort_dir=sort_dir,
            include_message_blocks=include_message_blocks,
            highlight=highlight,
            term_clauses=term_clauses,
            modifiers=modifiers,
            include_archived_channels=include_archived_channels,
            disable_semantic_search=disable_semantic_search,
        )
        try:
            response = client.api_call('assistant.search.context', json=params)
        except SlackApiError as error:
            return {'error': f'Slack search failed: {error}'}
        messages = response.get('results', {}).get('messages', [])
        allowed_channel_ids = set(scoped_channel_ids) if scoped_channel_ids else set(WHITELISTED_CHANNELS)
        return [
            self._format(message)
            for message in messages
            if message.get('channel_id') in allowed_channel_ids
        ]

    def _resolve_all(self, channel_refs):
        if not channel_refs:
            return channel_refs
        return [self.channel_resolver.resolve(ref) or ref for ref in channel_refs]

    def _build_params(self, channel_ids, query, limit, **optional_params):
        params = {
            'query': self._scope_to_channels(channel_ids, query),
            'content_types': self.FORCED_CONTENT_TYPES,
            'limit': min(limit, self.MAX_RESULTS),
        }
        for name, value in optional_params.items():
            if value is not None:
                params[name] = value
        return params

    def _scope_to_channels(self, channel_ids, query):
        # channel_ids has already been validated against WHITELISTED_CHANNELS
        # by search() before this is called, so it's safe to use as-is here.
        channels = channel_ids or WHITELISTED_CHANNELS
        modifiers = ' OR '.join(f'in:<#{cid}>' for cid in channels)
        return f'{query} {modifiers}'.strip()

    def _format(self, message):
        channel_name = message.get('channel_name') or message.get('channel_id')
        return {
            'channel': channel_name,
            'channel_id': message.get('channel_id'),
            'user': message.get('author_name') or message.get('author_user_id'),
            'is_bot': message.get('is_author_bot', False),
            'text': message.get('content'),
            'permalink': message.get('permalink'),
            'ts': message.get('message_ts'),
            'context': self._format_context(message.get('context_messages')),
        }

    def _format_context(self, context_messages):
        if not context_messages:
            return None
        return {
            'before': [self._format_context_message(m) for m in context_messages.get('before') or []],
            'after': [self._format_context_message(m) for m in context_messages.get('after') or []],
        }

    def _format_context_message(self, message):
        # Slack's own docs example for this endpoint shows the key as
        # `"user_id:"` (trailing colon, likely a docs typo) — check both so a
        # doc-accurate response doesn't silently lose the author.
        return {
            'user': message.get('user_id') or message.get('user_id:'),
            'text': message.get('text'),
            'ts': message.get('ts'),
        }


__all__ = ['SlackChannelSearchAssistantService']
