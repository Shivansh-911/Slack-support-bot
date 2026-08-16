"""Builds a local, process-lifetime cache of the workspace's user directory via
`users.list`, and searches it with a two-tier match: an exact case-insensitive
substring match first — the same semantics the MCP server's own `users_search`
tool already applies to name/real_name/display_name/email — falling back to
fuzzy/typo-tolerant matching only when that comes back empty.

This exists because substring matching, however permissive, still can't catch
a misspelling ("Jenifer" for "Jennifer") or a short form that isn't literally
contained in any profile field ("Jen" is a substring of "Jennifer" and matches
fine already; a genuine nickname like "Jay" for "Jennifer" is not, and no
substring-only approach — upstream's or a reimplementation of it — will ever
catch that without a hardcoded nickname dictionary, which this deliberately
does not carry).

No static name data lives in this codebase: `users.list` is the single source,
fetched fresh per process (see the identical trade-off documented in
SlackChannelResolverService — a rename/rejoin mid-process won't be reflected
until the next restart, an acceptable cost given how rarely profile names
change). The directory is never handed to the agent in full — only the
specific matches for its query — for the same reason `channels_list` isn't
exposed as a raw enumeration tool: the whole roster is more than any one
question needs.
"""

import difflib
import http.client

from django.conf import settings
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


class SlackUserDirectoryService:
    _directory_cache = None  # list of dicts, shared across instances/process
    FUZZY_CUTOFF = 0.6  # difflib similarity ratio floor below which a fuzzy hit is discarded

    def search(self, query, limit=10):
        """Returns up to `limit` users matching query, each carrying a
        `match_type` of 'exact' (substring, high confidence) or 'fuzzy'
        (typo/near-miss — only tried when 'exact' finds nothing, and worth
        treating as tentative rather than certain)."""
        if not query:
            return []
        directory = self._directory()
        exact = self._exact_matches(query, directory)
        if exact:
            return exact[:limit]
        return self._fuzzy_matches(query, directory)[:limit]

    def by_ids(self, user_ids):
        """Returns {user_id: directory_entry} for whichever of user_ids are
        actually in the directory (deleted/unknown users are simply absent,
        not an error)."""
        index = {user['user_id']: user for user in self._directory()}
        return {uid: index[uid] for uid in user_ids if uid in index}

    def _exact_matches(self, query, directory):
        needle = query.lower()
        return [
            {**user, 'match_type': 'exact'}
            for user in directory
            if needle in user['name'].lower()
            or needle in user['real_name'].lower()
            or needle in user['display_name'].lower()
            or needle in user['email'].lower()
        ]

    def _fuzzy_matches(self, query, directory):
        needle = query.lower()
        scored = []
        for user in directory:
            tokens = self._tokens(user)
            if not tokens:
                continue
            best_ratio = max(difflib.SequenceMatcher(None, needle, token).ratio() for token in tokens)
            if best_ratio >= self.FUZZY_CUTOFF:
                scored.append((best_ratio, {**user, 'match_type': 'fuzzy'}))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [user for _, user in scored]

    def _tokens(self, user):
        # Compare the query against individual name words, not whole strings —
        # "Jenifer" vs. the single token "jennifer" scores far better than
        # "Jenifer" vs. the full "jennifer hynes", which is what actually
        # makes a one-word typo catchable.
        tokens = set()
        for field in (user['name'], user['real_name'], user['display_name']):
            tokens.update(field.lower().split())
        return tokens

    def _directory(self):
        if SlackUserDirectoryService._directory_cache is None:
            SlackUserDirectoryService._directory_cache = self._fetch_directory()
        return SlackUserDirectoryService._directory_cache

    def _fetch_directory(self):
        client = WebClient(token=settings.SLACK_USER_TOKEN)
        directory = []
        cursor = None
        try:
            while True:
                response = client.users_list(cursor=cursor, limit=200)
                for member in response.get('members', []):
                    if member.get('deleted'):
                        continue
                    profile = member.get('profile', {})
                    directory.append({
                        'user_id': member.get('id'),
                        'name': member.get('name') or '',
                        'real_name': member.get('real_name') or '',
                        'display_name': profile.get('display_name') or '',
                        'email': profile.get('email') or '',
                        'is_bot': member.get('is_bot', False),
                    })
                cursor = response.get('response_metadata', {}).get('next_cursor')
                if not cursor:
                    break
        except (SlackApiError, http.client.HTTPException):
            # Fail closed on partial data: whatever was gathered before the
            # error is still cached and searched — a truncated directory
            # means fewer matches, not a crash. http.client.HTTPException
            # covers transient reads like IncompleteRead, which slack_sdk
            # doesn't wrap as a SlackApiError.
            pass
        return directory


__all__ = ['SlackUserDirectoryService']
