"""Formats a SlackChannelMembersService member-ID list into a compact text
block instead of raw JSON.

The IDs are unresolved (see SlackChannelMembersService's docstring), so
there's no per-member structure to break into blocks the way
SlackSearchResultFormatter does — a single comma-joined line covers it.
"""


class SlackChannelMembersFormatter:
    EMPTY_MESSAGE = "No members found."

    def format(self, member_ids):
        member_ids = member_ids or []
        if not member_ids:
            return self.EMPTY_MESSAGE
        return f"{len(member_ids)} member(s): " + ", ".join(member_ids)


__all__ = ["SlackChannelMembersFormatter"]
