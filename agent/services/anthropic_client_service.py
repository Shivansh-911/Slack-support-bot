"""Builds the configured Anthropic API client used for agent sessions."""

import anthropic
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class AnthropicClientService:
    def build(self):
        if not settings.ANTHROPIC_API_KEY:
            raise ImproperlyConfigured(
                'ANTHROPIC_API_KEY is not set. The agent cannot start a session '
                'without it.'
            )
        return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


__all__ = ['AnthropicClientService']
