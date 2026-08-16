"""Django app configuration for the Claude Managed Agents integration."""

from django.apps import AppConfig


class AgentConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'agent'


__all__ = ['AgentConfig']
