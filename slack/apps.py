from django.apps import AppConfig


class SlackConfig(AppConfig):
    name = 'slack'

    def ready(self):
        from slack.bolt_app import bolt_app
        from slack.services import SlackEventListenerService

        SlackEventListenerService().register(bolt_app)
