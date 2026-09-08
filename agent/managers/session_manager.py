"""Provides database query and mutation operations for session records."""

from django.db import models
from django.utils import timezone


class SessionManager(models.Manager):

    def find_by_thread(self, team_id, channel_id, thread_ts):
        """Returns the session backing this Slack thread, if one exists."""
        return self.filter(
            team_id=team_id,
            channel_id=channel_id,
            thread_ts=thread_ts,
        ).first()

    def create(self, team_id, channel_id, thread_ts, cma_session_id):
        return super().create(
            team_id=team_id,
            channel_id=channel_id,
            thread_ts=thread_ts,
            cma_session_id=cma_session_id,
            status=self.model.Status.RUNNING,
            last_used_at=timezone.now(),
        )

    def mark_running(self, session):
        session.status = self.model.Status.RUNNING
        session.last_used_at = timezone.now()
        session.save(update_fields=['status', 'last_used_at'])
        return session


    def session_stop(self, session, session_details):
        agent_id = session_details.agent.id
        list_cost =  session_details.usage.list_cost.amount
        session.agent_id = agent_id
        session.usage = list_cost
        session.status = self.model.Status.IDLE
        session.save(update_fields=['status','agent_id','usage'])
        return session

__all__ = ['SessionManager']
