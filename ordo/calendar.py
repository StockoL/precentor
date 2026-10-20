"""
Which celebration is kept on each day of the Ordinary Form calendar.

The rules follow the General Norms for the Liturgical Year and the
Calendar (1969), nos. 59 to 61, as romcal applies them, with one rule
romcal leaves out (see resolve_year). docs/calendar_plan.md explains
the design and docs/acknowledgements.md the sources.

A day's result is a list: the celebration kept, then anything still
observed alongside it, such as an obligatory memorial that falls on a
weekday of Lent and so becomes optional. Everything else that day is
impeded and left out, except a solemnity, which moves.

Occasions entered by hand have no precedence. They take no part in
the rules and are added at the end of their day, so a conductor's own
entries always show up.
"""

from collections import defaultdict
from datetime import timedelta

from .dates import NATIONAL_SETTINGS, YearDates

DAY = timedelta(days=1)

TRIDUUM = 1
PRIVILEGED_WEEKDAY = 9
MEMORIAL_LEVELS = {10, 11}
# Optional memorials aren't listed (docs/calendar_plan.md, section 5).
OPTIONAL_MEMORIAL = 12
# A solemnity that's impeded moves to the nearest day not taken by a day
# of these levels (General Norms, no. 60).
LEVELS_A_SOLEMNITY_CANNOT_MOVE_TO = set(range(1, 9))


def level(occasion):
    """The precedence level as a number: "8c" is 8."""
    return int(occasion.precedence.rstrip("abcdef"))


def precedence_key(occasion):
    """
    Sorts a day's occasions with the one kept first: by level, then by
    the letter within it. Between days still equal, the Proper of Time
    comes first, then a day whose date moves with the seasons (the
    Immaculate Heart of Mary with the Sacred Heart, or the Eternal High
    Priest with Pentecost) ahead of a fixed one, and finally the key, so
    the result never depends on the order rows come from the database.
    """
    code = occasion.precedence
    number = str(level(occasion))
    moves = bool(occasion.date_rule) or occasion.is_moveable
    return (
        int(number),
        code[len(number):],
        0 if occasion.is_proper_of_time else 1,
        0 if moves else 1,
        occasion.key,
    )


def kept_alongside(celebration, others, day, dates):
    """The other occasions of a day still observed with its celebration."""
    top = level(celebration)
    memorials = [o for o in others if level(o) in MEMORIAL_LEVELS]
    if dates.palm_sunday() <= day <= dates.holy_saturday():
        # No memorial is kept in Holy Week (GIRM 355a).
        memorials = []
    if top == PRIVILEGED_WEEKDAY:
        # On a weekday of Lent, 17 to 24 December or the Christmas Octave,
        # an obligatory memorial may still be kept as optional.
        return memorials
    if top in MEMORIAL_LEVELS:
        # Of two memorials, both are kept only when the first allows it;
        # otherwise the first prevails, as Mary, Mother of the Church
        # does (Congregation for Divine Worship, notification of 2018).
        return memorials if celebration.shares_with_memorials else []
    if top == TRIDUUM:
        # Holy Thursday is a weekday of Lent until the evening Mass of
        # the Lord's Supper begins the Triduum.
        return [o for o in others if o.rank == "weekday"]
    return []


def occasions_in_calendar(calendar_use, national_calendar):
    """The general calendar's occasions for one form, with the national
    calendar's added and its overrides replacing the general ones by key."""
    from .models import LiturgicalOccasion

    calendars = {"general_roman", national_calendar}
    rows = LiturgicalOccasion.objects.filter(calendar_use=calendar_use, calendar__in=calendars)
    by_key = {}
    unkeyed = []
    for occasion in rows:
        if not occasion.key:
            unkeyed.append(occasion)
        elif occasion.calendar == national_calendar or occasion.key not in by_key:
            by_key[occasion.key] = occasion
    return list(by_key.values()) + unkeyed


def resolve_year(year, calendar_use="current", national_calendar="general_roman", occasions=None):
    """
    {date: [celebration, then anything kept alongside it]} for every
    date in a civil year that has an occasion.

    Where this differs from romcal: a solemnity that's impeded and has no transfer of its
    own moves to the nearest following day not taken by a day of levels
    1 to 8 (General Norms, no. 60). romcal leaves such a solemnity out
    for the year; in 2022 it dropped the Nativity of St John the Baptist,
    which clashed with the Sacred Heart.
    """
    if occasions is None:
        occasions = occasions_in_calendar(calendar_use, national_calendar)
    dates = YearDates(year, NATIONAL_SETTINGS[national_calendar])

    ranked = defaultdict(list)
    unranked = defaultdict(list)
    for occasion in occasions:
        if occasion.precedence and level(occasion) == OPTIONAL_MEMORIAL:
            continue
        day = occasion.date_in(dates)
        if day is None or day.year != year:
            continue
        (ranked if occasion.precedence else unranked)[day].append(occasion)

    result = {}
    impeded_solemnities = []
    for day in sorted(ranked):
        celebration, *others = sorted(ranked[day], key=precedence_key)
        result[day] = [celebration, *kept_alongside(celebration, others, day, dates)]
        impeded_solemnities += [(day, o) for o in others if o.rank == "solemnity"]

    for day, solemnity in impeded_solemnities:
        target = day + DAY
        while target in result and level(result[target][0]) in LEVELS_A_SOLEMNITY_CANNOT_MOVE_TO:
            target += DAY
        if target.year != year:
            continue
        displaced = result.get(target, [])
        result[target] = [solemnity, *kept_alongside(solemnity, displaced, target, dates)]

    for day, entries in unranked.items():
        result.setdefault(day, []).extend(entries)
    return result
