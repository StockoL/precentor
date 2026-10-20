"""
The Ordinary Form's date rules: when each day of the liturgical year
falls in a given civil year.

Each LiturgicalOccasion either has a fixed month and day, or names one
of the rules below in `date_rule`, with any arguments in
`date_rule_args` and a number of days to add in `date_offset_days`
(the Thursday after Ash Wednesday is `ash_wednesday` plus 1). Transfers
then move a day in the years it would clash with something greater.

The rules are ported from romcal (MIT; see docs/calendar_plan.md), and
their names are romcal's in snake case, so its data converts without a
hand-kept mapping. As in romcal, a day of the week given as an argument
counts Sunday as 0.

A few rules depend on the national calendar: whether Epiphany,
Ascension and Corpus Christi move to a Sunday, and whether 6 January
moves to the nearest Sunday when it falls on certain weekdays. Those
settings are in NATIONAL_SETTINGS.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from functools import cached_property

from .utils import calculate_easter_sunday

DAY = timedelta(days=1)
WEEK = timedelta(days=7)

# Python's weekday() numbers, for the settings below.
MONDAY, SATURDAY = 0, 5


@dataclass(frozen=True)
class NationalSettings:
    epiphany_on_sunday: bool = False
    ascension_on_sunday: bool = False
    corpus_christi_on_sunday: bool = False
    # Weekdays on which 6 January moves to the nearest Sunday.
    epiphany_to_nearest_sunday_on: frozenset = field(default_factory=frozenset)


NATIONAL_SETTINGS = {
    "general_roman": NationalSettings(),
    "england": NationalSettings(
        corpus_christi_on_sunday=True,
        epiphany_to_nearest_sunday_on=frozenset({SATURDAY, MONDAY}),
    ),
    "wales": NationalSettings(
        corpus_christi_on_sunday=True,
        epiphany_to_nearest_sunday_on=frozenset({SATURDAY, MONDAY}),
    ),
}


def sunday_index(day):
    """Day of the week with Sunday as 0, as romcal and the data count."""
    return (day.weekday() + 1) % 7


def sunday_on_or_before(day):
    return day - sunday_index(day) * DAY


def days_between(start, end):
    """Every date from start to end inclusive."""
    return [start + n * DAY for n in range((end - start).days + 1)]


class YearDates:
    """The dates of the liturgical year falling in one civil year."""

    def __init__(self, year, settings=NATIONAL_SETTINGS["general_roman"]):
        self.year = year
        self.settings = settings

    def date_for(self, rule, args=(), offset=0):
        """A rule's date this year plus offset days, or None if the day
        doesn't occur this year (a seventh weekday of Ordinary Time, for
        example)."""
        method = getattr(self, rule, None)
        if method is None or rule.startswith("_") or rule in NOT_RULES:
            raise ValueError(f"Unknown date rule: {rule}")
        result = method(*args)
        return result + offset * DAY if result else None

    # Easter and the days counted from it

    @cached_property
    def _easter(self):
        return calculate_easter_sunday(self.year)

    def easter_sunday(self):
        return self._easter

    def ash_wednesday(self):
        return self._easter - 46 * DAY

    def palm_sunday(self):
        return self._easter - WEEK

    def holy_thursday(self):
        return self._easter - 3 * DAY

    def good_friday(self):
        return self._easter - 2 * DAY

    def holy_saturday(self):
        return self._easter - DAY

    def divine_mercy_sunday(self):
        return self._easter + WEEK

    def ascension(self):
        return self._easter + (42 if self.settings.ascension_on_sunday else 39) * DAY

    def pentecost_sunday(self):
        return self._easter + 49 * DAY

    def mary_mother_of_the_church(self):
        return self._easter + 50 * DAY

    def trinity_sunday(self):
        return self._easter + 56 * DAY

    def corpus_christi(self):
        return self._easter + (63 if self.settings.corpus_christi_on_sunday else 60) * DAY

    def most_sacred_heart_of_jesus(self):
        return self._easter + 68 * DAY

    def immaculate_heart_of_mary(self):
        return self._easter + 69 * DAY

    def weekday_or_sunday_of_easter_time(self, dow, week):
        """A day of Easter Time by week (1 to 7) and day of the week; none
        on the day the Ascension takes."""
        if not (1 <= week <= 7 and 0 <= dow <= 6):
            return None
        day = self._easter + ((week - 1) * 7 + dow) * DAY
        return None if day == self.ascension() else day

    # Advent and Christmas

    def christmas(self):
        return date(self.year, 12, 25)

    @cached_property
    def _first_sunday_of_advent(self):
        # The fourth Sunday before Christmas Day.
        christmas = self.christmas()
        return christmas - (sunday_index(christmas) or 7) * DAY - 3 * WEEK

    def sunday_of_advent(self, week):
        if not 1 <= week <= 4:
            return None
        return self._first_sunday_of_advent + (week - 1) * WEEK

    def privileged_weekday_of_advent(self, day):
        """17 to 24 December, except a Sunday."""
        if not 17 <= day <= 24:
            return None
        result = date(self.year, 12, day)
        return None if sunday_index(result) == 0 else result

    def holy_family(self):
        christmas = self.christmas()
        if sunday_index(christmas) == 0:
            return date(self.year, 12, 30)
        return sunday_on_or_before(christmas + WEEK)

    def weekday_within_octave_of_christmas(self, day_of_octave):
        """The nth day of the Christmas Octave, unless it's Holy Family."""
        if not 1 <= day_of_octave <= 8:
            return None
        result = self.christmas() + (day_of_octave - 1) * DAY
        return None if result == self.holy_family() else result

    def mary_mother_of_god(self):
        return date(self.year, 1, 1)

    @cached_property
    def _epiphany(self):
        first = date(self.year, 1, 1)
        result = date(self.year, 1, 6)
        if self.settings.epiphany_on_sunday:
            # The Sunday from 2 to 8 January.
            if sunday_index(first) == 6:
                result = first + DAY
            elif sunday_index(first) == 0:
                result = first + WEEK
            else:
                result = sunday_on_or_before(first + WEEK)
        if result.weekday() in self.settings.epiphany_to_nearest_sunday_on:
            after = sunday_index(result)
            result = result - after * DAY if after <= 7 - after else result + (7 - after) * DAY
        return result

    def epiphany(self):
        return self._epiphany

    @cached_property
    def _baptism_of_the_lord(self):
        epiphany = self._epiphany
        # On 7 or 8 January, Epiphany leaves no Sunday before Ordinary
        # Time, so the Baptism of the Lord is the Monday after it.
        if epiphany.day != 6 and (
            (sunday_index(epiphany) == 0 and epiphany.day == 7) or epiphany.day == 8
        ):
            return epiphany + DAY
        return sunday_on_or_before(epiphany + WEEK)

    def baptism_of_the_lord(self):
        return self._baptism_of_the_lord

    def second_sunday_after_christmas(self):
        """A Sunday between 2 January and the Baptism of the Lord that
        isn't Epiphany; only when Epiphany is kept on 6 January."""
        if self.settings.epiphany_on_sunday:
            return None
        before = days_between(date(self.year, 1, 2), self._epiphany - DAY)
        after = days_between(self._epiphany + DAY, self._baptism_of_the_lord - DAY)
        return next((d for d in before + after if sunday_index(d) == 0), None)

    # Ordinary Time

    @cached_property
    def _ordinary_time(self):
        """{week: {day of week: date or None}}, ported from romcal's
        dateOfOrdinaryTime, quirks included: see the comments."""
        early = days_between(self._baptism_of_the_lord + DAY, self.ash_wednesday() - DAY)
        late = days_between(self.pentecost_sunday() + DAY, self._first_sunday_of_advent - DAY)
        # Weeks after Pentecost are numbered back from Christ the King,
        # the 34th and last Sunday.
        late_start = int(35 - (len(late) + 1) / 7)
        baptism_on_monday = self._baptism_of_the_lord.weekday() == MONDAY
        # These take a Sunday or weekday of Ordinary Time, which then
        # isn't kept that year.
        replaced = {self.trinity_sunday(), self.corpus_christi(), self.most_sacred_heart_of_jesus()}

        def by_week(dates, is_early):
            weeks = {}
            for index, day in enumerate(dates):
                dow = sunday_index(day)
                if is_early:
                    week = index // 7 + (2 if dow == 0 else 1)
                    # Ordinary Time starts on the Tuesday when the Baptism is
                    # on the Monday, so that Monday belongs to the next week.
                    if baptism_on_monday and dow == 1:
                        week += 1
                else:
                    week = late_start + index // 7 + (1 if dow == 0 else 0)
                weeks.setdefault(week, {})[dow] = None if day in replaced else day
            return weeks

        # As in romcal, a week that has days both before Lent and after
        # Pentecost keeps only the later days.
        return {**by_week(early, True), **by_week(late, False)}

    def date_of_ordinary_time(self, dow, week):
        return self._ordinary_time.get(week, {}).get(dow)

    # Fixed solemnities and feasts with rules of their own

    def annunciation(self):
        """25 March, or the Monday after Divine Mercy Sunday when it falls
        in Holy Week or the Easter Octave."""
        result = date(self.year, 3, 25)
        if self.palm_sunday() <= result <= self.divine_mercy_sunday():
            return self.divine_mercy_sunday() + DAY
        return result

    def immaculate_conception_of_mary(self):
        """8 December, or the Monday when it falls on a Sunday of Advent."""
        result = date(self.year, 12, 8)
        return result + DAY if sunday_index(result) == 0 else result

    def nativity_of_john_the_baptist(self):
        return date(self.year, 6, 24)

    def peter_and_paul_apostles(self):
        return date(self.year, 6, 29)

    def assumption(self):
        return date(self.year, 8, 15)

    def all_saints(self):
        return date(self.year, 11, 1)

    def presentation_of_the_lord(self):
        return date(self.year, 2, 2)

    def transfiguration(self):
        return date(self.year, 8, 6)

    def exaltation_of_the_holy_cross(self):
        return date(self.year, 9, 14)


# Methods on YearDates that aren't date rules.
NOT_RULES = {"date_for"}


def rule_names():
    """Every date rule the data may name."""
    return sorted(
        name
        for name in vars(YearDates)
        if not name.startswith("_") and name not in NOT_RULES and callable(getattr(YearDates, name))
    )


def apply_transfers(day, transfers, dates):
    """
    Move a date by the occasion's transfers. Each transfer has a
    condition, tested against the original date, and a destination; as
    in romcal, the last one that matches wins.

    Conditions: {"if_day_of_week": 0} (Sunday as 0), or
    {"if_between": {"from": RULE, "to": RULE, "inclusive": true}}.
    Destinations: {"add_days": n}, counted from the original date, or a
    RULE, which is {"rule": name, "add_days": n}.
    """
    if day is None:
        return None
    moved = day
    for transfer in transfers:
        if "if_day_of_week" in transfer:
            matches = sunday_index(day) == transfer["if_day_of_week"]
        else:
            span = transfer["if_between"]
            start = dates.date_for(span["from"]["rule"], offset=span["from"].get("add_days", 0))
            end = dates.date_for(span["to"]["rule"], offset=span["to"].get("add_days", 0))
            if span.get("inclusive", True):
                matches = start <= day <= end
            else:
                matches = start < day < end
        if matches:
            then = transfer["then"]
            if "rule" in then:
                moved = dates.date_for(then["rule"], offset=then.get("add_days", 0))
            else:
                moved = day + then.get("add_days", 0) * DAY
    return moved
