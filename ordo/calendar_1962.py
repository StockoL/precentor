"""
The 1962 calendar: which celebration each day keeps, under the rubrics
of 1960.

Ported from Missalemeum's calendar (api/kalendar/factory.py and
rules.py; copyright 2022 Marcin Molenda, MIT licence: the notice is in
MISSALEMEUM_LICENSE.txt beside this file, and docs/acknowledgements.md
says how it was used). The steps and the rules are Missalemeum's, in
its order. What differs is the data they work on: Missalemeum matches
patterns against IDs such as "sancti:12-08:1:w", with the class and
colour inside them; here each day is a LiturgicalOccasion row with a
key ("sancti:12-08") and its class and colour as fields, and the rules
test those fields. docs/calendar_plan.md lists where the results
differ, and why.

The year is built in three steps:

1. Lay out the Proper of Time ("tempora") from the blocks in
   ordo/data/missalemeum/blocks_1962.json: the Sundays after Epiphany
   until Septuagesima (those it skips are resumed in November), the
   season from Septuagesima to the last Sunday after Pentecost, Advent,
   the September Ember Days and a few single days.
2. Add the saints ("sancti") on their dates.
3. Go through the year a day at a time and apply the first rule that
   fits, which decides the celebration and any commemorations, and may
   move a first-class feast to a later day.

Fourth-class days take part in the rules but aren't listed, like
optional memorials in the Ordinary Form.
"""

import json
import re
from collections import defaultdict
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

from .utils import calculate_easter_sunday

DAY = timedelta(days=1)
SUNDAY, SATURDAY = 6, 5  # Python weekday() numbers
BLOCKS_FILE = Path(__file__).resolve().parent / "data" / "missalemeum" / "blocks_1962.json"


@lru_cache(maxsize=1)
def blocks():
    return json.loads(BLOCKS_FILE.read_text(encoding="utf-8"))


# The dates Missalemeum's factory works the layout from.

def holy_family(year):
    """The Sunday after 6 January."""
    epiphany = date(year, 1, 6)
    return epiphany + timedelta(days=6 - epiphany.weekday() if epiphany.weekday() < 6 else 7)


def septuagesima(year):
    return calculate_easter_sunday(year) - timedelta(days=63)


def first_sunday_of_advent(year):
    """27 November if it's a Sunday, otherwise the Sunday after it."""
    day = date(year, 11, 27)
    return day + timedelta(days=(6 - day.weekday()) % 7)


def last_sunday_after_pentecost(year):
    return first_sunday_of_advent(year) - timedelta(days=7)


def ember_wednesday_of_september(year):
    """The Wednesday after the third Sunday of September (1960 rubrics)."""
    day = date(year, 9, 15)
    while day.weekday() != SUNDAY:
        day += DAY
    return day + timedelta(days=3)


def holy_name(year):
    """The first Sunday of the year, or 2 January when that Sunday falls
    on 1, 6 or 7 January."""
    day = date(year, 1, 1)
    while day.weekday() != SUNDAY:
        day += DAY
    return date(year, 1, 2) if day.day in (1, 6, 7) else day


def christ_the_king(year):
    """The last Sunday of October."""
    day = date(year, 10, 31)
    while day.weekday() != SUNDAY:
        day -= DAY
    return day


def sunday_in_christmas_octave(year):
    """The Sunday from 26 to 31 December, if there is one."""
    for offset in range(6):
        day = date(year, 12, 26) + timedelta(days=offset)
        if day.weekday() == SUNDAY:
            return day
    return None


@lru_cache(maxsize=64)
def tempora_layout(year):
    """
    {date: (tempora keys, celebration keys)} for the Proper of Time,
    before the saints are added. Ported from Missalemeum's
    _fill_in_tempora_days and _insert_block, with the same order of
    insertion, since later blocks overwrite earlier ones.
    """
    data = blocks()
    tempora = {}
    celebration = {}

    def insert(start, rows, stop=None, reverse=False, overwrite=True):
        if reverse:
            rows = list(reversed(rows))
        for index, keys in enumerate(rows):
            day = start + timedelta(days=-index if reverse else index)
            if not keys:
                continue
            if celebration.get(day) and not overwrite:
                break
            if stop is not None and stop == day - DAY:
                break
            tempora[day] = list(keys)
            celebration[day] = list(keys)

    insert(holy_family(year), data["post_epiphany"])
    insert(septuagesima(year), data["from_pre_lent_to_post_pentecost"])
    # Sundays after Epiphany that Septuagesima left out are resumed before
    # the last Sunday after Pentecost, counting back from it.
    insert(last_sunday_after_pentecost(year) - DAY, data["post_epiphany"], reverse=True, overwrite=False)
    insert(last_sunday_after_pentecost(year), data["week_24_after_pentecost"])
    insert(first_sunday_of_advent(year), data["advent"], stop=date(year, 12, 23))
    insert(ember_wednesday_of_september(year), data["ember_days_september"])

    celebration[holy_name(year)] = [data["holy_name"]]
    celebration[christ_the_king(year)] = [data["christ_the_king"]]
    octave_sunday = sunday_in_christmas_octave(year)
    if octave_sunday:
        insert(octave_sunday, data["nativity_octave_sunday"])
    for day in (29, 30, 31):
        insert(date(year, 12, day), data["nativity_octave_feria"], overwrite=False)

    days = set(tempora) | set(celebration)
    return {day: (tempora.get(day, []), celebration.get(day, [])) for day in days}


class YearDates1962:
    """The 1962 date rules for one civil year, in the same shape as
    ordo.dates.YearDates, so LiturgicalOccasion.date_in() works with
    either form."""

    def __init__(self, year):
        self.year = year

    def date_for(self, rule, args=(), offset=0):
        if rule == "christ_the_king_1962":
            result = christ_the_king(self.year)
        elif rule == "tempora_1962":
            (name,) = args
            key = f"tempora:{name}"
            matches = sorted(d for d, (tempora, _) in tempora_layout(self.year).items() if key in tempora)
            result = matches[0] if matches else None
        else:
            raise ValueError(f"Unknown 1962 date rule: {rule}")
        return result + offset * DAY if result else None


# The days and patterns the rules and the precedence table name. Keys
# are Missalemeum IDs without their class and colour, copied from its
# api/constants/common.py (some carry a suffix: "08-09t", "06-28r").

NATIVITY_VIGIL = "sancti:12-24"
NATIVITY_MASSES = ("sancti:12-25m1", "sancti:12-25m2", "sancti:12-25m3")
ALL_SOULS_MASSES = ("sancti:11-02m1", "sancti:11-02m2", "sancti:11-02m3")
ST_MATTHIAS = "sancti:02-24"
FEB_27 = "sancti:02-27"
VIGIL_OF_ST_LAWRENCE = "sancti:08-09t"
VIGIL_OF_ST_LAWRENCE_COMMEMORATED = "sancti:08-09cc"
FRIDAY_AFTER_PASSION_SUNDAY = "tempora:Quad5-5Feria"
SEVEN_SORROWS = "tempora:Quad5-5Feriac"
IMMACULATE_CONCEPTION = "sancti:12-08"
BAPTISM_OF_THE_LORD = "sancti:01-13"
FIRST_SUNDAY_AFTER_EPIPHANY = "tempora:Epi1-0"
ST_MICHAEL = "sancti:09-29"
SS_PETER_AND_PAUL = "sancti:06-29"
EXALTATION_OF_THE_CROSS = "sancti:09-14"
LATERAN_BASILICA = "sancti:11-09"
FIRST_CLASS_FERIAS = (
    "tempora:Quad6-1", "tempora:Quad6-2", "tempora:Quad6-3", "tempora:Quad6-4r",
    "tempora:Quad6-5r", "tempora:Quad6-6r", "tempora:Pasc0-0", "tempora:Quadp3-3",
)
EMBER_DAYS = (
    "tempora:Quad1-3", "tempora:Quad1-5", "tempora:Quad1-6",
    "tempora:093-3", "tempora:093-5", "tempora:093-6",
    "tempora:Adv3-3", "tempora:Adv3-5", "tempora:Adv3-6",
)
FEASTS_OF_THE_LORD_CLASS_1_AND_2 = ("sancti:01-06", BAPTISM_OF_THE_LORD, "sancti:02-02", "sancti:08-06")
FIXED_VIGILS_SUPPRESSED_ON_SUNDAY = ("sancti:06-23", "sancti:06-28r", VIGIL_OF_ST_LAWRENCE, "sancti:08-14")


class Observance:
    """One occasion on one date, as the rules see it."""

    def __init__(self, occasion, day):
        self.occasion = occasion
        self.key = occasion.key
        self.kind, self.name = occasion.key.split(":", 1)
        self.rank = int(occasion.rank.removeprefix("class_"))
        # Advent weekdays from 17 to 23 December are second class.
        if self.is_advent_feria() and day.month == 12 and 17 <= day.day <= 23:
            self.rank = 2
        self.priority = priority(self)

    def __repr__(self):
        return f"<{self.key}:{self.rank}>"

    @property
    def is_tempora(self):
        return self.kind == "tempora"

    @property
    def is_sancti(self):
        return self.kind == "sancti"

    def is_advent(self):
        return self.is_tempora and bool(re.match(r"Adv\d", self.name))

    def is_advent_feria(self):
        return self.is_tempora and bool(re.match(r"Adv\d-[1-6]", self.name))

    def is_advent_sunday(self):
        return self.is_tempora and bool(re.match(r"Adv\d-0", self.name))

    def is_lent(self):
        return self.is_tempora and bool(re.match(r"Quad(p3-[3-6]|\d)", self.name))

    def is_lent_sunday(self):
        return self.is_tempora and bool(re.match(r"Quad\d-0", self.name))

    def is_sunday(self):
        return self.is_tempora and bool(re.fullmatch(r".*-0r*", self.name))

    def is_second_class_sunday(self):
        return self.is_tempora and ((self.is_sunday() and self.rank == 2) or self.name == "Nat1-0")

    def is_national(self):
        """A day of a national calendar, standing in for Missalemeum's
        local (Polish) third-class saints."""
        return self.occasion.calendar != "general_roman"


# Missalemeum's Table of Precedence (from api/constants/common.py): the
# first entry that fits gives the priority, lower first.
PRECEDENCE_TABLE = (
    # First class
    *NATIVITY_MASSES, "tempora:Pasc0-0", "tempora:Pasc7-0",
    "tempora:Quad6-4r", "tempora:Quad6-5r", "tempora:Quad6-6r", "sancti:01-06",
    "tempora:Pasc5-4", "tempora:Pent01-0r", "tempora:Pent01-4", "tempora:Pent02-5",
    "sancti:10-DU", IMMACULATE_CONCEPTION, "sancti:08-15", NATIVITY_VIGIL, "sancti:01-01",
    Observance.is_advent_sunday, Observance.is_lent_sunday,
    "tempora:Pasc1-0", "tempora:Quadp3-3", "tempora:Quad6-1", "tempora:Quad6-2", "tempora:Quad6-3",
    *ALL_SOULS_MASSES, "tempora:Pasc6-6",
    "tempora:Pasc0-1", "tempora:Pasc0-2", "tempora:Pasc0-3", "tempora:Pasc0-4", "tempora:Pasc0-5", "tempora:Pasc0-6",
    "tempora:Pasc7-1", "tempora:Pasc7-2", "tempora:Pasc7-3", "tempora:Pasc7-4", "tempora:Pasc7-5", "tempora:Pasc7-6",
    lambda o: o.rank == 1,
    # Second class
    "tempora:Pasc5-3", BAPTISM_OF_THE_LORD, "sancti:08-06",
    Observance.is_second_class_sunday,
    lambda o: o.rank == 2,
    "sancti:12-26", "sancti:12-27", "sancti:12-28", "sancti:12-29", "sancti:12-31",
    # Third class: the weekdays of Lent, except the Ember Days
    "tempora:Quad1-1", "tempora:Quad1-2", "tempora:Quad1-4",
    *(f"tempora:Quad{week}-{day}" for week in (2, 3, 4) for day in range(1, 7)),
    "tempora:Quad5-1", "tempora:Quad5-2", "tempora:Quad5-3", "tempora:Quad5-4",
    FRIDAY_AFTER_PASSION_SUNDAY, "tempora:Quad5-6",
    lambda o: o.rank == 3,
    # Fourth class
    lambda o: True,
)


def priority(observance):
    for position, entry in enumerate(PRECEDENCE_TABLE):
        if entry == observance.key if isinstance(entry, str) else entry(observance):
            return position
    return len(PRECEDENCE_TABLE)


def first(observances, test):
    """The first observance that passes a test: a key, a tuple of keys,
    or a function. Missalemeum's match_first."""
    return next((o for o in observances if fits(o, test)), None)


def every(observances, test):
    return [o for o in observances if fits(o, test)]


def fits(observance, test):
    if isinstance(test, str):
        return observance.key == test
    if isinstance(test, tuple):
        return observance.key in test
    return test(observance)


# The rules, in Missalemeum's order. Each returns None if it doesn't
# apply, or (celebration, commemoration, moves), where moves is a list of
# (date, [observances]) to add to later days.

def rule_nativity_vigil(year, day, tempora, observances):
    # The Vigil of Christmas takes the place of the 4th Sunday of Advent.
    vigil = first(observances, NATIVITY_VIGIL)
    if vigil and day.weekday() == SUNDAY:
        return [vigil], [], []


def rule_nativity_has_three_masses(year, day, tempora, observances):
    if first(observances, NATIVITY_MASSES[0]):
        return every(observances, NATIVITY_MASSES), [], []


def rule_all_souls(year, day, tempora, observances):
    # 2 November, or 3 November when the 2nd is a Sunday; three Masses.
    if first(observances, ALL_SOULS_MASSES[0]):
        masses = every(observances, ALL_SOULS_MASSES)
        if day.weekday() == SUNDAY:
            return [first(observances, Observance.is_sunday)], [], [(date(day.year, 11, 3), masses)]
        return masses, [], []


def rule_st_matthias(year, day, tempora, observances):
    # 24 February, or the 25th in a leap year.
    matthias = first(observances, ST_MATTHIAS)
    if matthias and day.year % 4 == 0 and (day.year % 100 != 0 or day.year % 400 == 0) and day.day == 24:
        return [first(observances, lambda o: o.is_tempora)], [], [(date(day.year, 2, 25), [matthias])]


def rule_feb27(year, day, tempora, observances):
    # 27 February, or the 28th in a leap year.
    feast = first(observances, FEB_27)
    if feast and day.year % 4 == 0 and (day.year % 100 != 0 or day.year % 400 == 0) and day.day == 27:
        return [first(observances, lambda o: o.is_tempora)], [], [(date(day.year, 2, 28), [feast])]


def rule_st_lawrence_vigil(year, day, tempora, observances):
    vigil = first(observances, VIGIL_OF_ST_LAWRENCE)
    if vigil:
        commemorated = first(observances, VIGIL_OF_ST_LAWRENCE_COMMEMORATED)
        if day.weekday() == SATURDAY:
            # Missalemeum keeps the Saturday Office of Our Lady, a
            # fourth-class day Precentor doesn't list.
            return [], [commemorated] if commemorated else [], []
        if day.weekday() == SUNDAY:
            return None
        return [vigil], [commemorated] if commemorated else [], []


def rule_seven_sorrows_on_friday_after_passion_sunday(year, day, tempora, observances):
    friday = first(observances, FRIDAY_AFTER_PASSION_SUNDAY)
    seven_sorrows = first(observances, SEVEN_SORROWS)
    if friday and seven_sorrows:
        return [friday], [seven_sorrows], []


def rule_same_class_feasts_take_over_advent_feria_and_ember_days(year, day, tempora, observances):
    advent_or_ember = day.weekday() != SUNDAY and first(
        observances, lambda o: o.key in EMBER_DAYS or o.is_advent()
    )
    if advent_or_ember:
        saint = first(observances, lambda o: o.is_sancti)
        if not saint:
            return [advent_or_ember], [], []
        if advent_or_ember.rank == saint.rank:
            return [saint], [advent_or_ember], []
        if advent_or_ember.rank < saint.rank:
            return [advent_or_ember], [saint], []


def rule_lent_commemoration(year, day, tempora, observances):
    lent = first(observances, Observance.is_lent)
    if lent:
        saints = sorted(every(observances, lambda o: o.is_sancti), key=lambda o: o.rank)
        if not saints:
            return [lent], [], []
        lowest = saints[0].rank
        if lent.rank == lowest:
            if lowest == 1:
                return None  # moved to another day by the next rule
            return [lent], saints, []
        if lent.rank > lowest:
            return saints[:1], saints[1:] + [lent], []


def rule_shift_conflicting_first_class_feasts(year, day, tempora, observances, calendar):
    # Of two first-class feasts, the one lower in the Table of Precedence
    # moves to the first day with no first- or second-class feast. The
    # Immaculate Conception, however, is kept over a Sunday of Advent
    # (General Rubrics, 15).
    if day == date(day.year, 12, 8) and day.weekday() == SUNDAY:
        return [first(observances, lambda o: o.is_sancti)], [first(observances, lambda o: o.is_tempora)], []

    first_class = [o for o in observances if o.rank == 1]
    if len(first_class) > 1:
        kept, moved = sorted(first_class, key=lambda o: o.priority)[:2]
        target = day + DAY
        while target.year == day.year:
            if not {1, 2} & {o.rank for o in calendar.everything_on(target)}:
                break
            target += DAY
        else:
            target = None
        return [kept], [], [(target, [moved])]


def rule_lord_feast1(year, day, tempora, observances):
    # A first-class feast of the Lord takes the place of the Sunday or
    # weekday it falls on, with no commemoration of the day.
    if first(observances, BAPTISM_OF_THE_LORD) and first(observances, FIRST_SUNDAY_AFTER_EPIPHANY):
        return [first(observances, FIRST_SUNDAY_AFTER_EPIPHANY)], [], []


def rule_lord_feast2(year, day, tempora, observances):
    if first(observances, FEASTS_OF_THE_LORD_CLASS_1_AND_2) and first(observances, Observance.is_second_class_sunday):
        return [first(observances, lambda o: o.is_sancti and o.rank in (1, 2))], [], []


def rule_first_class_feast_with_sunday_commemoration(year, day, tempora, observances):
    # Some first-class feasts keep a commemoration of the Sunday, as St
    # Michael did on Sunday 29 September 2019.
    if first(observances, (ST_MICHAEL, SS_PETER_AND_PAUL)) and first(observances, Observance.is_second_class_sunday):
        return [first(observances, lambda o: o.rank == 1)], [first(observances, Observance.is_second_class_sunday)], []


def rule_first_class_feast_no_commemoration(year, day, tempora, observances):
    if first(observances, lambda o: o.rank == 1):
        return [first(sorted(observances, key=lambda o: o.priority), lambda o: o.rank == 1)], [], []


def rule_second_class_feast_no_sunday_commemoration(year, day, tempora, observances):
    # A few second-class feasts take over a second-class Sunday outright.
    if first(observances, (EXALTATION_OF_THE_CROSS, LATERAN_BASILICA)) and day.weekday() == SUNDAY:
        return [first(observances, lambda o: o.is_sancti and o.rank == 2)], [], []


def rule_fixed_vigils_suppressed_on_sunday(year, day, tempora, observances):
    if day.weekday() == SUNDAY and first(observances, FIXED_VIGILS_SUPPRESSED_ON_SUNDAY):
        sunday = first(observances, Observance.is_sunday)
        if sunday:
            return [sunday], [], []


def rule_second_class_sunday(year, day, tempora, observances):
    # A second-class Sunday is kept over a second-class feast, which is
    # commemorated; anything lower is left out.
    sunday = first(observances, Observance.is_second_class_sunday)
    if sunday and day.weekday() == SUNDAY:
        feast = first(observances, lambda o: o.is_sancti and o.rank == 2)
        return [sunday], [feast] if feast else [], []


def rule_first_class_feria(year, day, tempora, observances):
    # Ash Wednesday, Holy Week and Easter Sunday always win.
    if first(observances, FIRST_CLASS_FERIAS):
        return [first(observances, lambda o: o.is_tempora)], [], []


def rule_national_third_class_saint_over_general(year, day, tempora, observances):
    # A national third-class saint is celebrated and a general third- or
    # fourth-class saint commemorated (Missalemeum's rule for local saints).
    national = [o for o in observances if o.is_sancti and o.rank == 3 and o.is_national()]
    if national:
        general = [o for o in observances if o.is_sancti and o.rank in (3, 4) and not o.is_national()]
        if general:
            return national, general, []


def rule_fourth_class_feria_removed(year, day, tempora, observances):
    feria = first(observances, lambda o: o.is_tempora and o.rank == 4)
    if feria:
        rest = [o for o in observances if o is not feria]
        return rest, every(observances, lambda o: o.is_sancti and o.rank == 4), []


def rule_fourth_class_only_commemorated(year, day, tempora, observances):
    saint = first(observances, lambda o: o.is_sancti and o.rank == 4)
    if saint:
        return [o for o in observances if o is not saint], [saint], []


def rule_general(year, day, tempora, observances):
    if not observances:
        return [], [], []
    if len(observances) == 1:
        return list(observances), [], []
    top, second = sorted(observances, key=lambda o: (o.priority, o.rank, o.kind))[:2]
    if top.is_sunday() or (tempora and second.key == tempora[0].key):
        return [top], [], []
    return [top], [second], []


RULES = (
    rule_nativity_vigil,
    rule_nativity_has_three_masses,
    rule_all_souls,
    rule_st_matthias,
    rule_feb27,
    rule_st_lawrence_vigil,
    rule_seven_sorrows_on_friday_after_passion_sunday,
    rule_same_class_feasts_take_over_advent_feria_and_ember_days,
    rule_lent_commemoration,
    rule_shift_conflicting_first_class_feasts,
    rule_lord_feast1,
    rule_lord_feast2,
    rule_first_class_feast_with_sunday_commemoration,
    rule_first_class_feast_no_commemoration,
    rule_second_class_feast_no_sunday_commemoration,
    rule_fixed_vigils_suppressed_on_sunday,
    rule_second_class_sunday,
    rule_first_class_feria,
    # Missalemeum's next rule keeps the Saturday Office of Our Lady on a
    # Saturday with only fourth-class days; it's left out, since its
    # result is never listed.
    rule_national_third_class_saint_over_general,
    rule_fourth_class_feria_removed,
    rule_fourth_class_only_commemorated,
    rule_general,
)


class Year1962:
    """The 1962 calendar of one civil year, built from occasion rows."""

    def __init__(self, year, occasions):
        self.year = year
        by_key = {o.key: o for o in occasions if o.key}
        sancti_by_date = defaultdict(list)
        for occasion in occasions:
            if occasion.key.startswith("sancti:") and occasion.fixed_month:
                if occasion.fixed_month == 2 and occasion.fixed_day == 29 and not _leap(year):
                    continue
                sancti_by_date[date(year, occasion.fixed_month, occasion.fixed_day)].append(occasion)

        self.tempora = {}
        self.celebration = {}
        self.commemoration = defaultdict(list)
        for day, (tempora_keys, celebration_keys) in tempora_layout(year).items():
            self.tempora[day] = [Observance(by_key[k], day) for k in tempora_keys if k in by_key]
            self.celebration[day] = [Observance(by_key[k], day) for k in celebration_keys if k in by_key]
        for day, saints in sancti_by_date.items():
            # In key order, as Missalemeum's list of saints is.
            saints = sorted(saints, key=lambda o: o.key)
            observances = self.celebration.get(day, []) + [Observance(o, day) for o in saints]
            # Missalemeum sorts by class, first class first, keeping the
            # order of equals.
            self.celebration[day] = sorted(observances, key=lambda o: o.rank)

    def everything_on(self, day):
        return self.tempora.get(day, []) + self.celebration.get(day, []) + self.commemoration.get(day, [])

    def resolve(self):
        """Apply the rules to each day in turn. Returns {date: [celebration,
        then commemorations]} of observances."""
        moved_in = defaultdict(list)
        result = {}
        day = date(self.year, 1, 1)
        while day.year == self.year:
            observances = self.celebration.get(day, []) + moved_in.pop(day, [])
            tempora = self.tempora.get(day, [])
            for rule in RULES:
                if rule is rule_shift_conflicting_first_class_feasts:
                    outcome = rule(self.year, day, tempora, observances, self)
                else:
                    outcome = rule(self.year, day, tempora, observances)
                if outcome is not None:
                    break
            celebration, commemoration, moves = outcome
            celebration = [o for o in celebration if o]
            commemoration = [o for o in commemoration if o]
            self.celebration[day] = celebration
            self.commemoration[day] = commemoration
            for target, moved in moves:
                if target is not None:
                    moved_in[target].extend(moved)
            if celebration or commemoration:
                result[day] = celebration + [o for o in commemoration if o not in celebration]
            day += DAY
        return result


def _leap(year):
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def resolve_year_1962(year, national_calendar="general_roman", occasions=None):
    """
    {date: [occasions]} for a civil year of the 1962 calendar: the
    celebration first, then the commemorations. Fourth-class days and
    occasions without a key (entered by hand) take no part in the rules;
    hand-entered ones are added at the end of their day.
    """
    from .calendar import occasions_in_calendar

    if occasions is None:
        occasions = occasions_in_calendar("historic", national_calendar)
    keyed = [o for o in occasions if o.key and o.rank.startswith("class_")]
    unkeyed = [o for o in occasions if not (o.key and o.rank.startswith("class_"))]

    resolved = Year1962(year, keyed).resolve()
    result = {}
    for day, observances in resolved.items():
        listed = [o.occasion for o in observances if o.rank <= 3]
        if listed:
            result[day] = listed

    if unkeyed:
        dates = YearDates1962(year)
        for occasion in unkeyed:
            day = occasion.date_in(dates)
            if day is not None and day.year == year:
                result.setdefault(day, []).append(occasion)
    return result
