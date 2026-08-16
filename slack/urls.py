"""Routes Slack Events API webhook requests to their handling view."""

from django.urls import path

from slack.views import SlackEventsView

urlpatterns = [
    path('events/', SlackEventsView.as_view(), name='slack-events'),
]
