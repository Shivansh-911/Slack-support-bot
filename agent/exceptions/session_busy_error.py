"""Raised when an inbound Slack event targets a session that is still running."""


class SessionBusyError(Exception):

    def __init__(self, session):
        super().__init__(f'Session {session.cma_session_id} is already running.')
        self.session = session


