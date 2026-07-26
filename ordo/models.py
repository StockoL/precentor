from datetime import date, timedelta

from django.db import models

from .utils import calculate_easter_sunday

COLOUR_CHOICES = [
    ("violet", "Violet"),
    ("red", "Red"),
    ("green", "Green"),
    ("white", "White/Gold"),
    ("rose", "Rose"),
]


class LiturgicalOccasion(models.Model):
    TRADITION_CHOICES = [  # noqa
        ("catholic", "Catholic"),
        ("cofe", "Church of England"),
    ]
    name = models.CharField(max_length=100)
    tradition = models.CharField(max_length=20, choices=TRADITION_CHOICES)
    is_moveable = models.BooleanField(default=False)
    fixed_month = models.PositiveSmallIntegerField(blank=True, null=True)
    fixed_day = models.PositiveSmallIntegerField(blank=True, null=True)
    easter_offset_days = models.IntegerField(blank=True, null=True)
    colour = models.CharField(max_length=20, choices=COLOUR_CHOICES, blank=True)

    class Meta:
        ordering = ["tradition", "name"]  # noqa

    def __str__(self):
        return f"{self.name} ({self.get_tradition_display()})"

    def date_for_year(self, year):
        """Return this occasion's actual date in a given calendar year."""
        if self.is_moveable:
            easter = calculate_easter_sunday(year)
            return easter + timedelta(days=self.easter_offset_days)
        return date(year, self.fixed_month, self.fixed_day)
