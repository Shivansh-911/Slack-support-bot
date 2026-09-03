"""Routes Slack Events API webhook requests and team-management API requests."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from slack.views import SlackEventsView, TeamViewSet

router = DefaultRouter()
router.register('teams', TeamViewSet, basename='team')

urlpatterns = [
    path('events/', SlackEventsView.as_view(), name='slack-events'),
    path('', include(router.urls)),
]
