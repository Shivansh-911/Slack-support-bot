"""Raised when Asana's REST API returns an error envelope or an unreadable response."""


class AsanaApiError(Exception):

    def __init__(self, message):
        super().__init__(message)


__all__ = ['AsanaApiError']
