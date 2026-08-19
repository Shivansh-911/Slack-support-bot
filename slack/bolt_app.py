"""Creates the shared Bolt app instance and its Django request handler.

Bolt's built-in `RequestVerification` and `UrlVerification` middleware replace the
hand-rolled signature check and `url_verification` challenge handling this app used
to do itself.
"""

from django.conf import settings
from slack_bolt import App
from slack_bolt.adapter.django import SlackRequestHandler

bolt_app = App(
    token=settings.SLACK_BOT_TOKEN,
    signing_secret=settings.SLACK_SIGNING_SECRET,
)
bolt_request_handler = SlackRequestHandler(bolt_app)
# SlackRequestHandler — Bolt's Django adapter that translates a Django HttpRequest into Bolt's internal request/response cycle.

