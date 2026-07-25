from datetime import date

from django.test import TestCase

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
