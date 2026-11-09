from datetime import date, timedelta

from django.db import models

from accounts.querysets import OrganisationQuerySet

from .dates import NATIONAL_SETTINGS, YearDates, apply_transfers, sunday_cycle
from .utils import calculate_easter_sunday

COLOUR_CHOICES = [
    ("violet", "Violet"),
    ("red", "Red"),
    ("green", "Green"),
    ("white", "White/Gold"),
    ("rose", "Rose"),
    ("black", "Black"),
]

CALENDAR_USE_CHOICES = [
    ("current", "Ordinary Form (Novus Ordo)"),
    ("historic", "Extraordinary Form (1962)"),
]

# Which calendar an occasion belongs to. A national calendar adds days
# to the general one and overrides some of its days, matched by key.
NATIONAL_CALENDAR_CHOICES = [
    ("general_roman", "General Roman Calendar"),
    ("england", "England"),
    ("wales", "Wales"),
]

RANK_CHOICES = [
    # Ordinary Form
    ("solemnity", "Solemnity"),
    ("sunday", "Sunday"),
    ("feast", "Feast"),
    ("memorial", "Memorial"),
    ("optional_memorial", "Optional memorial"),
    ("weekday", "Weekday"),
    # 1962
    ("class_1", "First class"),
    ("class_2", "Second class"),
    ("class_3", "Third class"),
    ("class_4", "Fourth class"),
]

# The Ordinary Form's Table of Liturgical Days (General Norms for the
# Liturgical Year and the Calendar, no. 59), highest first. A lower
# number wins; letters order the days within a level. Precentor leaves
# optional memorials (level 12) out; the level exists so a national
# calendar can make a general memorial optional, as England does with St
# Elizabeth of Hungary.
OF_PRECEDENCE_CHOICES = [
    ("1", "1: The Paschal Triduum"),
    (
        "2",
        "2: Christmas, Epiphany, Ascension, Pentecost; Sundays of Advent, Lent and Easter; "
        "Ash Wednesday; Holy Week; the Easter Octave",
    ),
    ("3", "3: Solemnities of the General Calendar; All Souls"),
    ("4a", "4a: Principal patron of the place or country"),
    ("4b", "4b: Dedication of one's own church"),
    ("4c", "4c: Title of one's own church"),
    ("4d", "4d: Title, founder or principal patron of an order"),
    ("5", "5: Feasts of the Lord in the General Calendar"),
    ("6", "6: Sundays of Christmas Time and Ordinary Time"),
    ("7", "7: Feasts of the General Calendar"),
    ("8a", "8a: Principal patron of the diocese"),
    ("8b", "8b: Dedication of the cathedral"),
    ("8c", "8c: Principal patron of the region or country"),
    ("8d", "8d: Title, founder or principal patron of an order"),
    ("8e", "8e: Other feasts proper to a church"),
    ("8f", "8f: Other feasts proper to a diocese or order"),
    ("9", "9: Advent weekdays from 17 December; the Christmas Octave; Lent weekdays"),
    ("10", "10: Obligatory memorials of the General Calendar"),
    ("11a", "11a: Memorial of a secondary patron"),
    ("11b", "11b: Other obligatory memorials proper to a diocese or order"),
    ("12", "12: Optional memorials"),
    ("13", "13: Other weekdays"),
]


class LiturgicalSeason(models.Model):
    name = models.CharField(max_length=50)

    class Meta:
        ordering = ["name"]  # noqa

    def __str__(self):
        return self.name


class UseType(models.Model):
    # Use types are a church's own words for how it uses music, so each
    # belongs to an organisation, unlike the shared calendar.
    organisation = models.ForeignKey(
        "accounts.Organisation", on_delete=models.CASCADE, related_name="use_types"
    )
    objects = OrganisationQuerySet.as_manager()
    name = models.CharField(max_length=50)

    class Meta:
        ordering = ["name"]  # noqa

    def __str__(self):
        return self.name


class LiturgicalOccasionQuerySet(models.QuerySet):
    def listable(self, national_calendar="general_roman", keep=()):
        """
        The occasions a conductor can choose from, in both forms: the
        general calendar with one national calendar's days added and its
        overrides in place of the general rows, plus occasions entered by
        hand. Another country's days, fourth-class days and optional
        memorials are left out, as they are from the suggestions. Anything
        in keep (the occasions already chosen) stays listed regardless.
        """
        listed = self.filter(calendar__in=["general_roman", national_calendar])
        if national_calendar != "general_roman":
            national_keys = self.filter(calendar=national_calendar).exclude(key="").values("key")
            listed = listed.exclude(calendar="general_roman", key__in=national_keys)
        listed = listed.exclude(rank__in=["class_4", "optional_memorial"]).exclude(precedence="12")
        keep = [pk for pk in keep if pk]
        if keep:
            listed = self.filter(models.Q(pk__in=listed.values("pk")) | models.Q(pk__in=keep))
        return listed.order_by("calendar_use", "name")


class LiturgicalOccasion(models.Model):
    name = models.CharField(max_length=100)
    # Stable identifier from the source data (romcal's id for the
    # Ordinary Form). Blank for an occasion entered by hand.
    key = models.CharField(max_length=100, blank=True)
    calendar_use = models.CharField(
        max_length=20, choices=CALENDAR_USE_CHOICES, default="current"
    )
    calendar = models.CharField(
        max_length=20, choices=NATIONAL_CALENDAR_CHOICES, default="general_roman"
    )
    rank = models.CharField(max_length=20, choices=RANK_CHOICES, blank=True)
    precedence = models.CharField(
        max_length=4, choices=OF_PRECEDENCE_CHOICES, blank=True
    )
    # The Proper of Time (the seasons, Sundays and feasts of the Lord with
    # moving dates) takes precedence over a saint's day of equal rank.
    is_proper_of_time = models.BooleanField(default=False)
    # A memorial that shares its day with another memorial, both kept as
    # optional (the Immaculate Heart of Mary). Otherwise, of two memorials
    # on one day, only the first is kept.
    shares_with_memorials = models.BooleanField(default=False)
    # A named date rule from ordo/dates.py, its arguments and any days
    # added: the 5th Sunday of Ordinary Time is "date_of_ordinary_time"
    # with [0, 5]. Blank means the fixed month and day, or the Easter
    # offset of an occasion entered by hand.
    date_rule = models.CharField(max_length=50, blank=True)
    date_rule_args = models.JSONField(default=list, blank=True)
    date_offset_days = models.SmallIntegerField(default=0)
    # Moves the day makes in some years, e.g. off a Sunday or out of
    # Holy Week; see docs/calendar_plan.md, section 3.
    transfers = models.JSONField(default=list, blank=True)
    is_moveable = models.BooleanField(default=False)
    fixed_month = models.PositiveSmallIntegerField(blank=True, null=True)
    fixed_day = models.PositiveSmallIntegerField(blank=True, null=True)
    easter_offset_days = models.IntegerField(blank=True, null=True)
    colour = models.CharField(max_length=20, choices=COLOUR_CHOICES, blank=True)
    season = models.ForeignKey(
        LiturgicalSeason,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="occasions",
    )

    objects = LiturgicalOccasionQuerySet.as_manager()

    class Meta:
        ordering = ["name"]  # noqa
        constraints = [
            # A national calendar overrides a general day by sharing its
            # key, so a key appears once per calendar and form.
            models.UniqueConstraint(
                fields=["calendar_use", "calendar", "key"],
                condition=~models.Q(key=""),
                name="unique_occasion_key_per_calendar",
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def choice_label(self):
        """The name in a list of choices, where the 1962 days need telling
        apart from the Ordinary Form's (Sts. Peter & Paul, Saints Peter and
        Paul)."""
        return f"{self.name} (1962)" if self.calendar_use == "historic" else self.name

    def date_for_year(self, year, national_calendar=None):
        """
        This occasion's date in a civil year, or None if it doesn't occur
        that year. Some rules depend on the national calendar (Corpus
        Christi on a Sunday, for one); without one given, the occasion's
        own calendar's settings apply.
        """
        if self.calendar_use == "historic":
            from .calendar_1962 import YearDates1962

            return self.date_in(YearDates1962(year))
        settings = NATIONAL_SETTINGS[national_calendar or self.calendar]
        return self.date_in(YearDates(year, settings))

    def date_in(self, dates):
        """This occasion's date in a prepared YearDates, which a caller
        working out a whole year can share across occasions."""
        if self.date_rule:
            day = dates.date_for(self.date_rule, self.date_rule_args, self.date_offset_days)
        elif self.is_moveable:
            day = dates.easter_sunday() + timedelta(days=self.easter_offset_days)
        else:
            day = date(dates.year, self.fixed_month, self.fixed_day)
        return apply_transfers(day, self.transfers, dates)


def occasion_for_date(target_date, calendar_use, national_calendar="general_roman"):
    """
    Reverse lookup: the occasions kept on target_date, the day's
    celebration first and then anything observed alongside it. The list
    may be empty. Dates come from rules, not database columns, so the
    whole year is worked out in Python (ordo/calendar.py), which is also
    what lets precedence and transferred solemnities be applied.
    """
    if calendar_use == "historic":
        from .calendar_1962 import resolve_year_1962

        return resolve_year_1962(target_date.year, national_calendar).get(target_date, [])
    from .calendar import resolve_year

    return resolve_year(target_date.year, calendar_use, national_calendar).get(target_date, [])


PROPER_CHANT_PARTS = [
    ("introit", "Introit"),
    ("gradual", "Gradual"),
    ("alleluia", "Alleluia"),
    ("tract", "Tract"),
    ("sequence", "Sequence"),
    ("offertory", "Offertory"),
    ("communion", "Communion"),
    # Chants outside the Mass's propers that some days have, often several
    # of: Palm Sunday's antiphons, hymn and responsory, the Easter Vigil's
    # canticles.
    ("antiphon", "Antiphon"),
    ("responsory", "Responsory"),
    ("hymn", "Hymn"),
    ("canticle", "Canticle"),
]

# A saint's day can fall in Lent or Eastertide, when its Mass sings a
# Tract, or Alleluias in place of the Gradual. Those forms are kept beside
# the usual one and chosen by the service's date.
PROPER_CHANT_SEASONS = [
    ("", "Any time"),
    ("septuagesima", "Septuagesima to Easter"),
    ("paschaltide", "Eastertide"),
]


class ProperChant(models.Model):
    """
    The name of one of a day's proper chants, such as the Introit "Ad te
    levavi" for the First Sunday of Advent. Shared reference data like the
    calendar, loaded by load_calendar, with no church of its own. It's
    matched to occasions by key, not a foreign key, as occasions are
    rebuilt from their files and a national calendar repeats a key to
    move a day, which still has the same Mass.
    """

    occasion_key = models.CharField(max_length=100)
    calendar_use = models.CharField(max_length=20, choices=CALENDAR_USE_CHOICES)
    part = models.CharField(max_length=20, choices=PROPER_CHANT_PARTS)
    season = models.CharField(max_length=20, choices=PROPER_CHANT_SEASONS, blank=True)
    # An Ordinary Form Sunday's chant for one year of the three-year cycle;
    # blank for any year.
    cycle = models.CharField(max_length=1, choices=[("A", "Year A"), ("B", "Year B"), ("C", "Year C")], blank=True)
    # Where a day has several chants of one part, the order they're sung
    # in; 0 for the rest. It only sorts them and is never shown.
    position = models.PositiveSmallIntegerField(default=0)
    incipit = models.CharField(max_length=100)
    source = models.CharField(max_length=100, help_text="Where it came from, e.g. Divinum Officium Tempora/Adv1-0")

    class Meta:
        ordering = ["occasion_key", "part", "position"]  # noqa
        constraints = [
            models.UniqueConstraint(
                fields=["calendar_use", "occasion_key", "part", "season", "cycle", "position"],
                name="one_proper_chant_per_part",
            ),
        ]

    def __str__(self):
        return f"{self.get_part_display()}: {self.incipit}"


def chant_season(day):
    """The season a 1962 Mass's chants follow on a date: from Septuagesima,
    nine Sundays before Easter, to Holy Saturday; then Eastertide, to the
    Saturday after Pentecost; otherwise none."""
    easter = calculate_easter_sunday(day.year)
    if easter - timedelta(days=63) <= day < easter:
        return "septuagesima"
    if easter <= day <= easter + timedelta(days=55):
        return "paschaltide"
    return ""


def proper_chants(occasion, day):
    """
    The names of the chants sung at an occasion's Mass on a date, as
    {part: [incipits in the order sung]}, in either form; most parts have
    one. A form marked for the date beats the usual one: in 1962 a saint's
    day in Lent has its Tract in place of the Alleluia, and in the Ordinary
    Form a Sunday can have its own chant for the year of the cycle.
    """
    if occasion is None:
        return {}
    # The seasons only matter to the 1962 saints' days, the cycle only to
    # the Ordinary Form.
    season = chant_season(day) if occasion.calendar_use == "historic" else ""
    cycle = sunday_cycle(day) if occasion.calendar_use == "current" else ""
    best = {}
    for chant in ProperChant.objects.filter(calendar_use=occasion.calendar_use, occasion_key=occasion.key):
        if chant.season not in ("", season) or chant.cycle not in ("", cycle):
            continue
        fit = (chant.season == season and season != "") + (chant.cycle == cycle and cycle != "")
        place = (chant.part, chant.position)
        if place not in best or fit > best[place][0]:
            best[place] = (fit, chant.incipit)
    chants = {}
    for (part, _), (_, incipit) in sorted(best.items()):
        chants.setdefault(part, []).append(incipit)
    # A saint's day in Lent sings its Lenten Tract in place of the Alleluia.
    # The Easter Vigil, whose Tract is its own and not the season's, has both.
    if any(part == "tract" and fit for (part, _), (fit, _) in best.items()):
        chants.pop("alleluia", None)
    return chants


# The Ordinary Form Sundays whose propers carry into the weekdays after
# them: those of Ordinary Time, Advent and Eastertide after its octave.
# Lent's weekdays have Masses of their own, as do 17 to 24 December and
# the octaves, which are occasions in their own right.
WEEKDAY_SUNDAYS = ("ordinary_time_", "sunday_of_the_word_of_god", "advent_", "divine_mercy_sunday", "easter_time_")


def weekday_sunday(day, national_calendar="general_roman"):
    """
    The Sunday whose propers an Ordinary Form weekday with nothing of its
    own sings, as in 1962: the one before it, if that Sunday is kept as a
    Sunday of Ordinary Time, Advent (to 16 December) or Eastertide. None
    otherwise, including on a Sunday or after one a feast replaced.
    """
    if day.weekday() == 6 or (day.month, day.day) >= (12, 17):
        return None
    sunday = day - timedelta(days=day.weekday() + 1)
    kept = occasion_for_date(sunday, "current", national_calendar)
    if kept and kept[0].rank == "sunday" and kept[0].key.startswith(WEEKDAY_SUNDAYS):
        return kept[0]
    return None
