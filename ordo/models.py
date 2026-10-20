from datetime import date, timedelta

from django.db import models

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
    calendar_use = models.CharField(
        max_length=20, choices=CALENDAR_USE_CHOICES, default="current"
    )
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

    def __str__(self):
        return self.name

    def date_for_year(self, year):
        """Return this occasion's actual date in a given calendar year."""
        if self.is_moveable:
            easter = calculate_easter_sunday(year)
            return easter + timedelta(days=self.easter_offset_days)
        return date(year, self.fixed_month, self.fixed_day)


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
