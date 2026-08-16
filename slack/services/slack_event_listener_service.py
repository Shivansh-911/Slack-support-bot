"""Registers Slack Events API listeners on the Bolt app.

`register` archives every event_callback payload (deduped by event_id) via a
global middleware before any listener runs, so nothing is lost for event types
without a dedicated listener. That same middleware short-circuits retried
deliveries entirely — Slack redelivers an event_id it didn't get a fast enough
200 for, and without stopping the chain there, a retry would re-run listeners
and, once a listener has a real side effect (like adding a reaction), fire that
side effect again.

Each listener method holds only that event type's behavior — Bolt routes to it
by type instead of an `if event.get('type') == ...` branch.
"""

import logging
import re

from slack_bolt.response import BoltResponse
from slack_sdk.errors import SlackApiError

from slack.services.slack_event_dispatch_service import SlackEventDispatchService
from slack.utils.slack_markdown_formatter import SlackMarkdownFormatter
from agent.exceptions import SessionBusyError
from agent.services.agent_run import AgentRunService
from agent.services.slack_channel_name_resolver_service import SlackChannelNameResolverService


logger = logging.getLogger(__name__)


class SlackEventListenerService:
    REACTION_EMOJI = 'eyes'
    BUSY_MESSAGE = "Still working on your last message in this thread — I'll get to this one right after."
    EMPTY_ANSWER_MESSAGE = "I didn't get a text response for that — could you rephrase or ask again?"
    MENTION_PATTERN = re.compile(r'<@\w+>')

    def register(self, bolt_app):
        bolt_app.middleware(self.archive_event)
        bolt_app.event('app_mention')(self.handle_app_mention)
        bolt_app.message()(self.handle_message)
        # Falls through to here for any event type without a specific listener
        # above. Without this, Bolt returns 404 for those (already archived by
        # the middleware) events, which reads to Slack as a failed delivery and
        # triggers retries.
        bolt_app.event(re.compile('.*'))(self.acknowledge_unhandled_event)

    def archive_event(self, body, next):
        is_new = SlackEventDispatchService().handle(body)
        if not is_new:
            return BoltResponse(status=200, body='')
        next()

    def handle_app_mention(self, ack, event, client, body):
        ack()
        self._react(client, event)
        team_id = body.get('team_id')
        channel_id = event.get('channel')
        channel_name = self._channel_name(channel_id)
        thread_ts = event.get('thread_ts') or event.get('ts')
        user_id = event.get('user')
        question = self._strip_question(event.get('text'))
        agent_run_service = AgentRunService()
        try:
            answer = agent_run_service.handle_run(
                channel_id, channel_name, thread_ts, team_id, user_id, question
            )
        except SessionBusyError:
            self._post(client, channel_id, thread_ts, self.BUSY_MESSAGE)
            return
        self._post(client, channel_id, thread_ts, answer)

    def handle_message(self, ack, event, client):
        ack()

    def acknowledge_unhandled_event(self, ack):
        ack()

    def _react(self, client, event):
        try:
            client.reactions_add(
                channel=event['channel'],
                timestamp=event['ts'],
                name=self.REACTION_EMOJI,
            )
        except SlackApiError as error:
            # e.g. already_reacted — a message that both mentions the bot and
            # matches the plain-message listener gets two react attempts for
            # the same ts; Slack rejects the second one, which is harmless.
            logger.warning('Could not add reaction: %s', error)

    def _channel_name(self, channel_id):
        resolved = SlackChannelNameResolverService().resolve(channel_id)
        if not resolved or isinstance(resolved, dict):
            return channel_id
        return resolved

    def _strip_question(self, text):
        return self.MENTION_PATTERN.sub('', text or '').strip()

    def _post(self, client, channel_id, thread_ts, text):
        formatted = SlackMarkdownFormatter().format(text) or self.EMPTY_ANSWER_MESSAGE
        try:
            client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                text=formatted,
            )
        except SlackApiError as error:
            logger.warning('Could not post message: %s', error)


__all__ = ['SlackEventListenerService']
