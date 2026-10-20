from datetime import date, timedelta

from django.db import models

from .dates import NATIONAL_SETTINGS, YearDates, apply_transfers

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
    ("weekday", "Weekday"),
    # 1962
    ("class_1", "First class"),
    ("class_2", "Second class"),
    ("class_3", "Third class"),
    ("class_4", "Fourth class"),
]

# The Ordinary Form's Table of Liturgical Days (General Norms for the
# Liturgical Year and the Calendar, no. 59), highest first. A lower
# number wins; letters order the days within a level. Level 12 (optional
# memorials) is left out, since Precentor doesn't carry them.
OF_PRECEDENCE_CHOICES = [
    ("1", "1: The Paschal Triduum"),
    ("2", "2: Christmas, Epiphany, Ascension, Pentecost; Sundays of Advent, Lent and Easter; Ash Wednesday; Holy Week; the Easter Octave"),
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
    ("13", "13: Other weekdays"),
]


class LiturgicalSeason(models.Model):
    name = models.CharField(max_length=50)

    class Meta:
        ordering = ["name"]  # noqa

    def __str__(self):
        return self.name


class UseType(models.Model):
    name = models.CharField(max_length=50)

    class Meta:
        ordering = ["name"]  # noqa

    def __str__(self):
        return self.name


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

    def date_for_year(self, year, national_calendar=None):
        """
        This occasion's date in a civil year, or None if it doesn't occur
        that year. Some rules depend on the national calendar (Corpus
        Christi on a Sunday, for one); without one given, the occasion's
        own calendar's settings apply.
        """
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


def occasion_for_date(target_date, calendar_use):
    """
    Reverse lookup: which LiturgicalOccasion(s) fall on target_date for a
    given calendar_use. date_for_year() is a Python method, not a
    database field, so candidates are scoped by calendar_use first (to
    keep the loop small) and then evaluated in Python. Returns a list —
    zero, one, or more occasions can share a date.
    """
    candidates = LiturgicalOccasion.objects.filter(calendar_use=calendar_use)
    return [
        occasion
        for occasion in candidates
        if occasion.date_for_year(target_date.year) == target_date
    ]
