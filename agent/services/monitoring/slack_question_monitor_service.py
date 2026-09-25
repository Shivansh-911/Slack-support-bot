"""Records one New Relic `SlackQuestion` custom event per Slack question.

The question's details only become known piece by piece — who asked and
where once the team is resolved, the CMA session once `handle_run` picks
one, the cost and tool totals once the run stops, the outcome once the
reply is posted — so one instance travels with the question from
`SlackEventListenerService.handle_message` into `AgentRunService.handle_run`
and back, collecting fields, and `record` writes them as a single event at
whichever exit the question takes. Custom events are used instead of
transaction custom attributes: they keep for 30 days rather than 8, and
hold values up to `custom_insights_events.max_attribute_value` (4095
bytes) rather than a fixed 255, so the full question fits.

The New Relic transaction itself is started by newrelic.ini's
`[background-task:slack-handle-message]` section. This class only renames
it per team and, for messages that aren't questions, drops it. Custom
events carry no link to the transaction they were recorded in, so the
event copies the trace id for dashboards to jump to the question's trace.

Costs are CMA `list_cost.amount` values, which are cents as strings — the
same value `SessionManager.session_stop` stores in `Session.usage`. The
per-question cost is the session total now minus the total stored before
this run, since a reused session's total spans every question in its
thread.
"""

import logging
import time

import newrelic.agent


logger = logging.getLogger(__name__)


class SlackQuestionMonitorService:
    EVENT_TYPE = 'SlackQuestion'
    TRANSACTION_GROUP = 'Slack'
    TRANSACTION_NAME_PRIORITY = 2
    OUTCOME_ANSWERED = 'answered'
    OUTCOME_EMPTY_ANSWER = 'empty_answer'
    OUTCOME_REACTED_ONLY = 'reacted_only'
    OUTCOME_BUSY = 'busy'
    OUTCOME_ERROR = 'error'

    def __init__(self):
        self.fields = {}
        self.recorded = False

    def ignore(self):
        try:
            newrelic.agent.ignore_transaction()
        except Exception:
            logger.warning('Could not ignore New Relic transaction', exc_info=True)

    def add_request_fields(
        self, slack_team_id, channel_id, user_id,
        thread_ts, message_ts, team, trigger_type, question,
    ):
        try:
            self._name_transaction(team)
            self.fields.update({
                'slack.team_id': slack_team_id,
                'slack.channel_id': channel_id,
                'slack.thread_ts': thread_ts,
                'slack.message_ts': message_ts,
                'slack.is_thread_reply': thread_ts != message_ts,
                'slack.user_id': user_id,
                'slack.agent_team': team.name,
                'slack.trigger': trigger_type,
                'slack.question': question,
                'slack.question_length': len(question or ''),
                'slack.queue_ms': self._queue_ms(message_ts),
            })
        except Exception:
            logger.warning('Could not collect New Relic request fields', exc_info=True)

    def add_session_fields(self, session_id, session_reused, agent_id):
        self.fields.update({
            'cma.session_id': session_id,
            'cma.session_reused': session_reused,
            'cma.agent_id': agent_id,
        })

    def add_cost_fields(self, previous_session_cost, session_details):
        try:
            session_cost = self._cents(session_details.usage.list_cost.amount)
            previous_cost = self._cents(previous_session_cost)
            self.fields.update({
                'cma.session_cost_cents': session_cost,
                'cma.turn_cost_cents': max(session_cost - previous_cost, 0.0),
            })
        except Exception:
            logger.warning('Could not collect New Relic cost fields', exc_info=True)

    def add_tool_counts(self, tool_call_count, tool_error_count):
        self.fields.update({
            'cma.tool_call_count': tool_call_count,
            'cma.tool_error_count': tool_error_count,
        })

    def record(self, outcome, message_ts):
        if self.recorded:
            return
        self.recorded = True
        try:
            self.fields.update({
                'slack.outcome': outcome,
                'slack.e2e_latency_ms': self._milliseconds_since(message_ts),
                'slack.processing_ms': self._processing_ms(),
                'trace.id': newrelic.agent.current_trace_id(),
            })
            newrelic.agent.record_custom_event(self.EVENT_TYPE, self.fields)
        except Exception:
            logger.warning('Could not record New Relic question event', exc_info=True)

    def notice_error(self):
        try:
            newrelic.agent.notice_error()
        except Exception:
            logger.warning('Could not report error to New Relic', exc_info=True)

    def _name_transaction(self, team):
        newrelic.agent.set_transaction_name(
            f'SlackAgent/{team.name}',
            group=self.TRANSACTION_GROUP,
            priority=self.TRANSACTION_NAME_PRIORITY,
        )

    def _transaction_start_time(self):
        transaction = newrelic.agent.current_transaction()
        return getattr(transaction, 'start_time', None)

    def _queue_ms(self, message_ts):
        started_at = self._transaction_start_time()
        if not message_ts or not started_at:
            return None
        return round((started_at - float(message_ts)) * 1000)

    def _processing_ms(self):
        started_at = self._transaction_start_time()
        if not started_at:
            return None
        return round((time.time() - started_at) * 1000)

    def _milliseconds_since(self, message_ts):
        if not message_ts:
            return None
        return round((time.time() - float(message_ts)) * 1000)

    def _cents(self, amount):
        try:
            return float(amount) if amount else 0.0
        except (TypeError, ValueError):
            return 0.0


__all__ = ['SlackQuestionMonitorService']
