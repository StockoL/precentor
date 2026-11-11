from datetime import date
from io import StringIO

from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from .batch import PICK, SUNDAYS_AND_GREAT_DAYS, candidates, pattern_choices

ADVENT_START, ADVENT_END = date(2026, 11, 29), date(2026, 12, 24)


class CandidateDatesTests(TestCase):
    """Which dates a batch offers, worked out from the real calendar."""

    @classmethod
    def setUpTestData(cls):
        call_command("load_calendar", stdout=StringIO())

    def dates(self, pattern, calendar_use="current", start=ADVENT_START, end=ADVENT_END):
        return [day for day, _ in candidates(start, end, pattern, calendar_use, "england")]

    def test_every_sunday_of_advent_and_the_range_ends_included(self):
        self.assertEqual(self.dates("sundays"), [
            date(2026, 11, 29), date(2026, 12, 6), date(2026, 12, 13), date(2026, 12, 20),
        ])
        # A range starting and ending on a Sunday keeps both ends.
        self.assertEqual(self.dates("sundays", end=date(2026, 12, 6)), [date(2026, 11, 29), date(2026, 12, 6)])

    def test_a_weekday_solemnity_comes_with_the_second_pattern_only(self):
        immaculate = date(2026, 12, 8)  # a Tuesday
        self.assertNotIn(immaculate, self.dates("sundays"))
        self.assertIn(immaculate, self.dates(SUNDAYS_AND_GREAT_DAYS))
        # The Vigil Mass is listed alongside 24 December's weekday, which isn't a solemnity.
        self.assertNotIn(date(2026, 12, 24), self.dates(SUNDAYS_AND_GREAT_DAYS))

    def test_in_1962_first_class_days(self):
        self.assertIn(date(2026, 12, 8), self.dates(SUNDAYS_AND_GREAT_DAYS, calendar_use="historic"))
        self.assertEqual(pattern_choices("historic")[1][1], "Sundays and first-class days")
        self.assertEqual(pattern_choices("current")[1][1], "Sundays and solemnities")

    def test_picking_offers_every_date(self):
        self.assertEqual(len(self.dates(PICK)), 26)

    def test_each_date_comes_with_its_celebration(self):
        found = dict(candidates(ADVENT_START, ADVENT_END, SUNDAYS_AND_GREAT_DAYS, "current", "england"))
        self.assertEqual(found[date(2026, 11, 29)].name, "First Sunday of Advent")
        self.assertEqual(found[date(2026, 12, 8)].name, "The Immaculate Conception of the Blessed Virgin Mary")

    def test_the_calendar_is_read_once_however_long_the_range(self):
        with CaptureQueriesContext(connection) as week:
            candidates(date(2026, 11, 29), date(2026, 12, 5), PICK, "current", "england")
        with CaptureQueriesContext(connection) as two_years:
            candidates(date(2026, 1, 1), date(2027, 12, 31), PICK, "current", "england")
        self.assertEqual(len(week), 1)
        self.assertEqual(len(two_years), len(week))
