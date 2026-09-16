"""Backs the `get_current_time` custom tool. Uses the same minute-level,
fixed-UTC format as AgentRunService._current_datetime() so a tool re-check
mid-turn never disagrees with the context message's current_datetime.
"""

from django.utils import timezone


class CurrentTimeService:
    FORMAT = '%Y-%m-%d %H:%M UTC (%A)'

    def get_current_time(self):
        return {'current_datetime': timezone.now().strftime(self.FORMAT)}


__all__ = ['CurrentTimeService']
