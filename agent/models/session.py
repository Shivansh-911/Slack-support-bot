"""Defines the Session model backing per-thread Claude Managed Agents sessions."""

from django.db import models

from agent.managers import SessionManager


class Session(models.Model):

    class Status(models.TextChoices):
        RUNNING = 'running', 'Running'
        IDLE = 'idle', 'Idle'

    team_id = models.CharField(max_length=64, blank=True, default='')
    channel_id = models.CharField(max_length=64, blank=True, default='')
    thread_ts = models.CharField(max_length=64, blank=True, default='')
    cma_session_id = models.CharField(max_length=128, blank=True, default='')
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.IDLE)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField()

    objects = SessionManager()

    class Meta:
        indexes = [
            models.Index(fields=['team_id', 'channel_id', 'thread_ts'], name='session_thread_idx'),
        ]


__all__ = ['Session']
