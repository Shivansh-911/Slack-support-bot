"""Fetches a Claude Managed Agents session's full event history, then writes it as JSON into resuts/sessions/<session_id>.json."""

import os
import sys
import json

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.conf import settings
from anthropic import Anthropic


class SessionRunExporter:
    SESSIONS_DIRECTORY = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sessions')

    def __init__(self, session_id):
        self.session_id = session_id
        self.client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    def export(self):
        self._write(self._fetch_events())

    def _fetch_events(self):
        events_page = self.client.beta.sessions.events.list(session_id=self.session_id)
        return [event.model_dump(mode='json') for event in events_page]

    def _write(self, events):
        os.makedirs(self.SESSIONS_DIRECTORY, exist_ok=True)
        output_path = os.path.join(self.SESSIONS_DIRECTORY, f'{self.session_id}.json')
        with open(output_path, 'w') as output_file:
            json.dump(events, output_file, indent=2, default=str)


if __name__ == '__main__':
    SessionRunExporter(session_id='sesn_01PVEDwXTMKmSZfLqcRY9Pm8').export()


__all__ = ['SessionRunExporter']
