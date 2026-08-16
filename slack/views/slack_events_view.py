"""Delegates incoming Slack Events API webhook requests to the Bolt app.

Deliberately a plain Django `View` rather than the DRF ViewSet this project
uses elsewhere. Bolt verifies Slack's signature over the raw request body, and
DRF parses that body during request handling, so routing this through DRF would
break signature verification. Do not "fix" this to match the other views.
"""

from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from slack.bolt_app import bolt_request_handler


@method_decorator(csrf_exempt, name='dispatch')
class SlackEventsView(View):
    def post(self, request, *args, **kwargs):
        return bolt_request_handler.handle(request)


__all__ = ['SlackEventsView']
