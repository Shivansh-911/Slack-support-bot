"""Shared helper for turning a list of Slack API records into one compact,
flattened text block instead of JSON.

Every Slack custom tool that returns a *list* of same-shaped records
(search results today; usergroups and others later) hits the same
problem with generic `json.dumps`: every field name is repeated on every
row, and the model has to re-parse nested structure it doesn't actually
need. Formatting each record into its own small text block and joining
those blocks with a plain separator is cheaper in tokens and closer to
the prose the agent has to produce anyway — no braces, quotes, or
repeated keys to parse through.

This module has no opinion on what a record looks like — that's each
tool's own formatter (e.g. SlackSearchResultFormatter). It only owns how
the resulting blocks are joined and what an empty result set says, so
that stays consistent across tools.
"""

SEPARATOR = "\n---\n"


def join_blocks(blocks, empty_message):
    blocks = [block for block in blocks if block]
    if not blocks:
        return empty_message
    return SEPARATOR.join(blocks)


__all__ = ["join_blocks"]
