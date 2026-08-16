"""Registers Slack app models with the Django admin site."""

from django.contrib import admin

from slack.models import SlackEvent

admin.site.register(SlackEvent)
