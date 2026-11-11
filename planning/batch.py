"""
The dates a batch of services could take, for adding several at once:
every Sunday in a range, Sundays and the great days, or every date for
the conductor to pick from, each with the day's celebration to set as
its occasion.

A solemnity is known by the rank of the day's kept celebration, not its
precedence level: in the Ordinary Form level 2 also holds the Sundays of
Advent, Lent and Easter and Ash Wednesday, and 1962 rows have no
precedence at all. The 1962 calendar has no solemnities, so there the
pattern takes first-class days, its nearest equivalent (decided 11
November 2026).
"""

from datetime import timedelta

from ordo.calendar import occasions_in_calendar, resolve_year
from ordo.calendar_1962 import resolve_year_1962

SUNDAY = 6
EVERY_SUNDAY = "sundays"
SUNDAYS_AND_GREAT_DAYS = "sundays_and_solemnities"
PICK = "pick"


def pattern_choices(calendar_use):
    """The patterns, the second named for the term's calendar."""
    great = "Sundays and first-class days" if calendar_use == "historic" else "Sundays and solemnities"
    return [(EVERY_SUNDAY, "Every Sunday"), (SUNDAYS_AND_GREAT_DAYS, great), (PICK, "I'll pick the dates")]


def kept_by_date(start, end, calendar_use, national_calendar):
    """
    {date: [the celebration kept, then anything alongside it]} for the
    range. The church's calendar is read once and each civil year the
    range touches is worked out once, rather than a lookup for each date,
    which would work out the whole year again every time.
    """
    occasions = occasions_in_calendar(calendar_use, national_calendar)
    kept = {}
    for year in range(start.year, end.year + 1):
        if calendar_use == "historic":
            kept.update(resolve_year_1962(year, national_calendar, occasions))
        else:
            kept.update(resolve_year(year, calendar_use, national_calendar, occasions))
    return kept


def is_great_day(occasion, calendar_use):
    """A solemnity, or in 1962 a first-class day."""
    return occasion.rank == ("class_1" if calendar_use == "historic" else "solemnity")


def candidates(start, end, pattern, calendar_use, national_calendar):
    """
    [(date, occasion or None)] in date order for the pattern. The occasion
    is the day's kept celebration, the first of its list, which is the one
    the single service form suggests too.
    """
    kept = kept_by_date(start, end, calendar_use, national_calendar)
    found = []
    day = start
    while day <= end:
        occasion = (kept.get(day) or [None])[0]
        wanted = (
            pattern == PICK
            or day.weekday() == SUNDAY
            or (pattern == SUNDAYS_AND_GREAT_DAYS and occasion is not None and is_great_day(occasion, calendar_use))
        )
        if wanted:
            found.append((day, occasion))
        day += timedelta(days=1)
    return found
