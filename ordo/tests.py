from datetime import date

from django.test import TestCase

from .models import LiturgicalOccasion, occasion_for_date
from .utils import calculate_easter_sunday


class CalculateEasterSundayTests(TestCase):
    """
    Verifies the computus implementation against published Easter
    Sunday dates. These are independently known, fixed calendar facts,
    not values derived from the code under test.
    """

    def test_known_easter_dates(self):
        known_dates = {
            2024: date(2024, 3, 31),
            2025: date(2025, 4, 20),
            2026: date(2026, 4, 5),
            2027: date(2027, 3, 28),
            2030: date(2030, 4, 21),
        }
        for year, expected in known_dates.items():
            with self.subTest(year=year):
                self.assertEqual(calculate_easter_sunday(year), expected)


class OccasionForDateTests(TestCase):
    def setUp(self):
        self.christmas = LiturgicalOccasion.objects.create(
            name="Christmas Day",
            tradition="cofe",
            calendar_use="current",
            fixed_month=12,
            fixed_day=25,
        )
        self.easter = LiturgicalOccasion.objects.create(
            name="Easter Day",
            tradition="cofe",
            calendar_use="current",
            is_moveable=True,
            easter_offset_days=0,
        )

    def test_matches_fixed_occasion(self):
        matches = occasion_for_date(date(2026, 12, 25), "cofe", "current")
        self.assertEqual(matches, [self.christmas])

    def test_matches_moveable_occasion(self):
        matches = occasion_for_date(date(2026, 4, 5), "cofe", "current")
        self.assertEqual(matches, [self.easter])

    def test_no_match_returns_empty_list(self):
        matches = occasion_for_date(date(2026, 6, 1), "cofe", "current")
        self.assertEqual(matches, [])

    def test_wrong_tradition_excluded(self):
        matches = occasion_for_date(date(2026, 12, 25), "catholic", "current")
        self.assertEqual(matches, [])

    def test_wrong_calendar_use_excluded(self):
        matches = occasion_for_date(date(2026, 12, 25), "cofe", "historic")
        self.assertEqual(matches, [])

    def test_multiple_occasions_on_same_date_both_returned(self):
        # A confirmed real scenario, not an edge case to ignore: two
        # distinct named occasions can legitimately share a calendar date.
        also_christmas = LiturgicalOccasion.objects.create(
            name="Nativity of the Lord",
            tradition="cofe",
            calendar_use="current",
            fixed_month=12,
            fixed_day=25,
        )
        matches = occasion_for_date(date(2026, 12, 25), "cofe", "current")
        self.assertEqual(set(matches), {self.christmas, also_christmas})
        self.assertEqual(len(matches), 2)
