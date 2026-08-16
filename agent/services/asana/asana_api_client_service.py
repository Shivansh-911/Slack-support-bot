"""Thin wrapper around Asana's REST API (`https://app.asana.com/api/1.0`).

Called only from Django, never from the agent's own sandbox — that sandbox has no
network egress at all (see cma/agent.yaml's note on the agent_toolset_20260401 block),
so this is the one place in the system that can actually reach app.asana.com. Every
response is unwrapped to its `data` payload; an `{"errors": [...]}` envelope, or a
non-2xx/non-JSON response, raises AsanaApiError instead of being handed back raw.
"""

import requests
from django.conf import settings

from agent.exceptions import AsanaApiError


class AsanaApiClientService:
    BASE_URL = 'https://app.asana.com/api/1.0'
    TIMEOUT_SECONDS = 30
    DEFAULT_PAGE_SIZE = 100

    def get(self, path, params=None):
        response = self._request(path, params)
        return response['data']

    def get_paginated(self, path, params, limit):
        results = []
        offset = None
        page_size = min(self.DEFAULT_PAGE_SIZE, limit) if limit else self.DEFAULT_PAGE_SIZE
        request_params = dict(params or {})
        request_params['limit'] = page_size
        while True:
            if offset:
                request_params['offset'] = offset
            response = self._request(path, request_params)
            page = response['data']
            remaining = limit - len(results) if limit else None
            results.extend(page if remaining is None else page[:remaining])
            if limit and len(results) >= limit:
                break
            offset = response.get('next_page', {}).get('offset') if response.get('next_page') else None
            if not offset:
                break
        return results

    def _request(self, path, params=None):
        try:
            response = requests.get(
                f'{self.BASE_URL}{path}',
                headers=self._headers(),
                params=params,
                timeout=self.TIMEOUT_SECONDS,
            )
        except requests.RequestException as error:
            raise AsanaApiError(f'Asana request failed: {error}')
        try:
            payload = response.json()
        except ValueError:
            raise AsanaApiError(f'Non-JSON response from Asana (status {response.status_code}).')
        if 'errors' in payload:
            messages = '; '.join(error.get('message', 'unknown error') for error in payload['errors'])
            raise AsanaApiError(f'Asana error: {messages}')
        if not response.ok:
            raise AsanaApiError(f'Asana request failed with status {response.status_code}.')
        return payload

    def _headers(self):
        return {
            'Authorization': f'Bearer {settings.ASANA_ACCESS_TOKEN}',
            'Accept': 'application/json',
        }


__all__ = ['AsanaApiClientService']
