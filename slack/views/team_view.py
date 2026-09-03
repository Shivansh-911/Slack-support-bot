"""Accepts a full team row over the API to insert or update it — for
managing teams on a deployment (e.g. Railway) where `manage.py
populate_teams` can't be run.

Looked up by `name` rather than the numeric id — there's no fetch
endpoint to look the id up with, and `name` is always known since it's
chosen when the team is created.
"""

from rest_framework import mixins, viewsets

from slack.models.teams import Teams
from slack.serializers.team_serializer import TeamSerializer


class TeamViewSet(mixins.CreateModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    queryset = Teams.objects.all()
    serializer_class = TeamSerializer
    lookup_field = 'name'


__all__ = ['TeamViewSet']
