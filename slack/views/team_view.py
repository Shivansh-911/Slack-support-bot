"""Accepts a full team row over the API and inserts it — for adding a team
on a deployment (e.g. Railway) where `manage.py populate_teams` can't be run.
"""

from rest_framework import mixins, viewsets

from slack.models.teams import Teams
from slack.serializers.team_serializer import TeamSerializer


class TeamViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    queryset = Teams.objects.all()
    serializer_class = TeamSerializer


__all__ = ['TeamViewSet']
