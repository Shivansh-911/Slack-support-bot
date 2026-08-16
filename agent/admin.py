"""Registers the agent app's models for inspection in the Django admin."""

from django.contrib import admin

from agent.models import Session

admin.site.register(Session)
