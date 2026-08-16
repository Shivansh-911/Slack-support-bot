"""Archives Slack Events API event_callback payloads, deduped by event_id.

`url_verification` handshakes never reach here — Bolt's built-in `UrlVerification`
middleware answers those before any listener is invoked. Per-event-type behavior
(e.g. app_mention) lives in listeners, not here — this only records that an event
happened.
"""

from slack.models import SlackEvent


class SlackEventDispatchService:
    def handle(self, payload):
        """Archives payload, returning False if event_id was already seen (a Slack retry)."""
        event_id = payload.get('event_id')
        if SlackEvent.objects.has_event_id(event_id):
            return False
        SlackEvent.objects.create_from_payload(payload)
        return True


__all__ = ['SlackEventDispatchService']
