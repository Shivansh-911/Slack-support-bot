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
    updated_at = models.DateTimeField(auto_now=True)

    objects = SessionManager()


__all__ = ['Session']
