"""Registers Slack Events API listeners on the Bolt app.

`register` archives every event_callback payload (deduped by event_id) via a
global middleware before any listener runs, so nothing is lost for event types
without a dedicated listener. That same middleware short-circuits retried
deliveries entirely — Slack redelivers an event_id it didn't get a fast enough
200 for, and without stopping the chain there, a retry would re-run listeners
and, once a listener has a real side effect (like adding a reaction), fire that
side effect again.

There is only one shared bot now, so there is no `app_mention` to listen for —
a team is invoked by mentioning that team's dedicated seat (a plain Slack
user, not this bot) inside an ordinary message. `handle_message` is the only
listener: it either resolves a fresh team mention, or falls back to the
session already on file for this thread when there is none. Either way, it
only ever reads a `Session` row — creating and reusing one stays inside
`AgentRunService`, so there is exactly one place that ever writes one.

A team's seat is a real Slack user, not a bot user, so every reply `_post`
sends under `team.slack_user_token` comes back through this same listener as
an ordinary `message` event — Slack only tags a message as `bot_message` for
an actual bot user, so nothing here does that filtering for us. Without the
early return on a team's own `slack_user_id`, the agent would answer its own
answer forever. Checked against every team's id up front, not just the
already-resolved one, since any team's seat posting anywhere must be
ignored the same way.
"""

import logging
import re

from slack_bolt.response import BoltResponse
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from agent.models.session import Session
from slack.services.slack_event_dispatch_service import SlackEventDispatchService
from slack.utils.slack_markdown_formatter import SlackMarkdownFormatter
from agent.exceptions import SessionBusyError
from agent.services.agent_run import AgentRunService
from agent.services.slack.slack_channel_service import SlackChannelService
from slack.models.teams import Teams


logger = logging.getLogger(__name__)


class SlackEventListenerService:
    REACTION_EMOJI = 'eyes'
    BUSY_MESSAGE = "Still working on your last message in this thread — I'll get to this one right after."
    EMPTY_ANSWER_MESSAGE = "I didn't get a text response for that — could you rephrase or ask again?"
    TRIGGER_MENTION = 'mention'
    TRIGGER_MESSAGE = 'message'

    def register(self, bolt_app):
        bolt_app.middleware(self.archive_event)
        bolt_app.message()(self.handle_message)
        bolt_app.event(re.compile('.*'))(self.acknowledge_unhandled_event)

    def archive_event(self, body, next):
        is_new = SlackEventDispatchService().handle(body)
        if not is_new:
            return BoltResponse(status=200, body='')
        next()

    def handle_message(self, ack, event, client, body):
        ack()

        text = event.get('text') or ''
        channel_id = event.get('channel')
        slack_team_id = body.get('team_id')
        thread_ts = event.get('thread_ts') or event.get('ts')
        message_ts = event.get('ts')
        user_id = event.get('user')

        if user_id in Teams.objects.get_team_ids():
            return

        team = self._resolve_mention(text)
        if team is not None:
            trigger_type = self.TRIGGER_MENTION
            question = self._strip_mention(text, team.slack_user_id)
        else:
            team = self._resolve_followup_team(slack_team_id, channel_id, thread_ts)
            if team is None:
                return
            trigger_type = self.TRIGGER_MESSAGE
            question = text

        all_channels = SlackChannelService()._fetch_id_to_name(team.slack_user_token)
        if channel_id not in all_channels:
            return

        self._react(channel_id, message_ts, team.slack_user_token)

        agent_run_service = AgentRunService()
        try:
            answer = agent_run_service.handle_run(
                channel_id,
                thread_ts,
                slack_team_id,
                user_id,
                question,
                message_ts,
                trigger_type,
                team,
                all_channels
            )
        except SessionBusyError:
            self._post(channel_id, thread_ts, self.BUSY_MESSAGE, team.slack_user_token)
            return
        if answer:
            self._post(channel_id, thread_ts, answer, team.slack_user_token)

        # answer = self._debug_run_summary(
            # channel_id, thread_ts, slack_team_id, user_id, question, message_ts, trigger_type, team, all_channels
        # )
        # self._post(channel_id, thread_ts, answer, team.slack_user_token)

    def _debug_run_summary(self, channel_id, thread_ts, slack_team_id, user_id, question, message_ts, trigger_type, team, all_channels):
        return (
            f'channel_id: {channel_id}\n'
            f'thread_ts: {thread_ts}\n'
            f'slack_team_id: {slack_team_id}\n'
            f'user_id: {user_id}\n'
            f'question: {question}\n'
            f'message_ts: {message_ts}\n'
            f'trigger_type: {trigger_type}\n'
            f'team: {team.name}\n'
            f'memory_stores: {team.cma_memory_id} and {team.cma_instructions_memory_id}\n'
            f'all_channels: {all_channels}'
        )

    def _resolve_mention(self, text):
        for slack_user_id in Teams.objects.get_team_ids():
            if re.search(f'<@{slack_user_id}>', text):
                return Teams.objects.fetch_team(slack_user_id)
        return None

    def _resolve_followup_team(self, slack_team_id, channel_id, thread_ts):
        session = Session.objects.existing_session(slack_team_id, channel_id, thread_ts)
        if not session:
            return None
        return Teams.objects.fetch_team_by_name(session.name)

    def acknowledge_unhandled_event(self, ack):
        ack()

    def _react(self, channel_id, message_ts, slack_user_token):
        client = WebClient(token=slack_user_token)
        try:
            client.reactions_add(
                channel=channel_id,
                timestamp=message_ts,
                name=self.REACTION_EMOJI,
            )
        except SlackApiError as error:
            logger.warning('Could not add reaction: %s', error)

    def _strip_mention(self, text, slack_user_id):
        return re.sub(f'<@{slack_user_id}>', '', text or '').strip()

    def _post(self, channel_id, thread_ts, text, slack_user_token):
        formatted = SlackMarkdownFormatter().format(text) or self.EMPTY_ANSWER_MESSAGE
        client = WebClient(token=slack_user_token)
        try:
            client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                text=formatted,
            )
        except SlackApiError as error:
            logger.warning('Could not post message: %s', error)


__all__ = ['SlackEventListenerService']
