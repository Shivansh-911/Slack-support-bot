"""Provides database query and mutation operations for session records."""

from django.db import models


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
        )

    def mark_running(self, session):
        session.status = self.model.Status.RUNNING
        session.save(update_fields=['status', 'updated_at'])
        return session

    def mark_idle(self, session):
        session.status = self.model.Status.IDLE
        session.save(update_fields=['status', 'updated_at'])
        return session


__all__ = ['SessionManager']
