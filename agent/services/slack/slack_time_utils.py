"""Deterministic date/time-string -> Unix timestamp conversion for the
Slack time-filter params (`before`/`after` on search_whitelisted_channels,
`oldest`/`latest` on conversations_history/conversations_replies).

These params used to be typed as raw integers in the agent-facing schema,
which meant the agent itself had to compute a Unix epoch number by mental
arithmetic from a human date — an error-prone step that produced wrong
search windows (e.g. "August" resolving to late-Aug-through-Sep). The
schema now takes a date/date-time string instead, and this module does the
actual epoch conversion server-side, deterministically.
"""

import re
from datetime import datetime, time as dt_time, timezone as dt_timezone

from django.utils.dateparse import parse_date, parse_datetime

_TRAILING_UTC_RE = re.compile(r'\s*UTC$', re.IGNORECASE)


def parse_to_unix_timestamp(value, *, end_of_day=False):
    """Parse a date or date-time string into a Unix timestamp (int seconds).

    Accepts ISO 8601 dates ("2026-08-31") and date-times ("2026-08-31T14:30:00Z",
    "2026-08-31 14:30:00+00:00", "2026-08-31 14:30:00"), including the
    "<date> <time> UTC" shape current_datetime is formatted in. A datetime
    with no timezone, or a bare date, is treated as UTC — every "now" this
    system hands an agent is already UTC, so there is no other timezone a
    caller could mean.

    A bare date with no time component resolves to 00:00:00 of that day by
    default, or 23:59:59 when end_of_day=True — pass end_of_day=True for an
    upper bound (`before`/`latest`) so the named day is included, and leave
    it False for a lower bound (`after`/`oldest`) so the day starts at 0:00.

    A raw int/float is passed through unchanged (already a Unix timestamp).
    Returns None for a falsy input. Raises ValueError if the string is
    neither a valid date nor a valid date-time.
    """
    if value in (None, ''):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(value)

    text = _TRAILING_UTC_RE.sub('', str(value).strip()).strip()

    # Check parse_date first: parse_datetime silently accepts a bare date
    # too (returning midnight), which would swallow the end_of_day case
    # below and never apply it to a date-only "before"/"latest" value.
    date_only = parse_date(text)
    if date_only is not None:
        parsed = datetime.combine(date_only, dt_time.max if end_of_day else dt_time.min)
    else:
        parsed = parse_datetime(text)
        if parsed is None:
            raise ValueError(f'Could not parse "{value}" as a date or date-time.')

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt_timezone.utc)

    return int(parsed.timestamp())


__all__ = ['parse_to_unix_timestamp']
