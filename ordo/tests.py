from datetime import date

from django.test import TestCase

from accounts.testing import make_organisation, make_user
from precentor_project.testing import make_use_type

from .models import (
    LiturgicalOccasion,
    LiturgicalSeason,
    UseType,
    occasion_for_date,
)
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


class SeededDataTests(TestCase):
    """The test database is built by running the migrations, so these
    check what the seed and revision migrations leave behind."""

    def test_a_new_database_starts_without_use_types(self):
        # 0004 and 0010 make Mass, Vespers and General use, then 0017
        # removes them again on a database with no organisations, since
        # each organisation gets its own copies when it registers.
        self.assertFalse(UseType.objects.exists())

    def test_seeded_seasons_are_the_roman_calendar_seasons(self):
        self.assertEqual(
            set(LiturgicalSeason.objects.values_list("name", flat=True)),
            {
                "Advent",
                "Christmas",
                "Ordinary Time",
                "Lent",
                "Easter Triduum",
                "Easter",
            },
        )


class CalendarUseLabelTests(TestCase):
    def test_labels_name_the_two_roman_rite_forms(self):
        occasion = LiturgicalOccasion(name="Christmas Day")
        occasion.calendar_use = "current"
        self.assertEqual(
            occasion.get_calendar_use_display(), "Ordinary Form (Novus Ordo)"
        )
        occasion.calendar_use = "historic"
        self.assertEqual(
            occasion.get_calendar_use_display(), "Extraordinary Form (1962)"
        )


class OccasionForDateTests(TestCase):
    def setUp(self):
        self.christmas = LiturgicalOccasion.objects.create(
            name="Christmas Day",
            calendar_use="current",
            fixed_month=12,
            fixed_day=25,
        )
        self.easter = LiturgicalOccasion.objects.create(
            name="Easter Day",
            calendar_use="current",
            is_moveable=True,
            easter_offset_days=0,
        )

    def test_matches_fixed_occasion(self):
        matches = occasion_for_date(date(2026, 12, 25), "current")
        self.assertEqual(matches, [self.christmas])

    def test_matches_moveable_occasion(self):
        matches = occasion_for_date(date(2026, 4, 5), "current")
        self.assertEqual(matches, [self.easter])

    def test_no_match_returns_empty_list(self):
        matches = occasion_for_date(date(2026, 6, 1), "current")
        self.assertEqual(matches, [])

    def test_wrong_calendar_use_excluded(self):
        matches = occasion_for_date(date(2026, 12, 25), "historic")
        self.assertEqual(matches, [])

    def test_multiple_occasions_on_same_date_both_returned(self):
        # A confirmed real scenario, not an edge case to ignore: two
        # distinct named occasions can legitimately share a calendar date.
        also_christmas = LiturgicalOccasion.objects.create(
            name="Nativity of the Lord",
            calendar_use="current",
            fixed_month=12,
            fixed_day=25,
        )
        matches = occasion_for_date(date(2026, 12, 25), "current")
        self.assertEqual(set(matches), {self.christmas, also_christmas})
        self.assertEqual(len(matches), 2)


class OccasionLookupViewTests(TestCase):
    def setUp(self):
        self.client.force_login(make_user("viewer"))
        self.christmas = LiturgicalOccasion.objects.create(
            name="Christmas Day",
            calendar_use="current",
            fixed_month=12,
            fixed_day=25,
        )

    def test_matching_date_returns_occasion(self):
        response = self.client.get(
            "/ordo/occasion-lookup/",
            {"date": "2026-12-25", "calendar_use": "current"},
        )
        self.assertEqual(response.status_code, 200)
        occasions = response.json()["occasions"]
        self.assertEqual(len(occasions), 1)
        self.assertEqual(occasions[0]["name"], "Christmas Day")

    def test_non_matching_date_returns_empty_list(self):
        response = self.client.get(
            "/ordo/occasion-lookup/",
            {"date": "2026-06-01", "calendar_use": "current"},
        )
        self.assertEqual(response.json()["occasions"], [])

    def test_invalid_date_returns_empty_list(self):
        response = self.client.get(
            "/ordo/occasion-lookup/",
            {"date": "not-a-date", "calendar_use": "current"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["occasions"], [])

    def test_invalid_calendar_use_returns_empty_list(self):
        response = self.client.get(
            "/ordo/occasion-lookup/",
            {"date": "2026-12-25", "calendar_use": "bogus"},
        )
        self.assertEqual(response.json()["occasions"], [])

    def test_requires_login(self):
        self.client.logout()
        response = self.client.get(
            "/ordo/occasion-lookup/",
            {"date": "2026-12-25", "calendar_use": "current"},
        )
        self.assertEqual(response.status_code, 302)


class OccasionKeyTests(TestCase):
    def make(self, calendar="general_roman", key="george_of_lydda_martyr"):
        return LiturgicalOccasion.objects.create(
            name="Saint George", key=key, calendar=calendar, fixed_month=4, fixed_day=23
        )

    def test_a_national_calendar_can_reuse_a_general_key(self):
        self.make()
        self.make(calendar="england")
        self.assertEqual(LiturgicalOccasion.objects.filter(key="george_of_lydda_martyr").count(), 2)

    def test_a_key_appears_once_in_each_calendar(self):
        from django.db import IntegrityError, transaction

        self.make()
        with transaction.atomic(), self.assertRaises(IntegrityError):
            self.make()

    def test_occasions_entered_by_hand_need_no_key(self):
        self.make(key="")
        self.make(key="")
        self.assertEqual(LiturgicalOccasion.objects.filter(key="").count(), 2)


class LiturgicalColourTokenTests(TestCase):
    def test_every_colour_choice_has_a_token_in_both_themes(self):
        # Templates build var(--colors-liturgical-<colour>) from the stored
        # value, so a choice without a token would quietly lose its colour.
        from pathlib import Path

        from django.conf import settings

        from .models import COLOUR_CHOICES

        css = (Path(settings.BASE_DIR) / "static/src/global/variables.css").read_text(encoding="utf-8")
        for value, _ in COLOUR_CHOICES:
            with self.subTest(colour=value):
                # Light, dark by system setting, and dark by choice.
                self.assertEqual(css.count(f"--colors-liturgical-{value}:"), 3)


class UseTypeOrganisationTests(TestCase):
    def test_a_use_type_belongs_to_an_organisation(self):
        church = make_organisation()
        use = make_use_type("Communion", organisation=church)
        self.assertEqual(list(church.use_types.all()), [use])


class FillUseTypeOrganisationTests(TestCase):
    """The fill-in migration, run against today's models while the column
    can still be empty. These go when the column becomes required."""

    def run_migration(self):
        import importlib

        from django.apps import apps

        importlib.import_module("ordo.migrations.0017_fill_use_type_organisation").give_use_types_an_organisation(apps, None)

    def test_with_no_organisation_unused_starters_go_and_tagged_ones_stay(self):
        from library.models import Score

        UseType.objects.create(name="Vespers")
        mass = UseType.objects.create(name="Mass")
        score = Score.objects.create(title="Missa brevis", composer_surname="Palestrina")
        score.suited_use_types.add(mass)
        self.run_migration()
        self.assertEqual(list(UseType.objects.values_list("name", flat=True)), ["Mass"])
        mass.refresh_from_db()
        self.assertEqual(mass.organisation.name, "My church")

    def test_with_an_organisation_every_use_type_joins_it(self):
        church = make_organisation("St Cecilia's")
        use = UseType.objects.create(name="Vespers")
        self.run_migration()
        use.refresh_from_db()
        self.assertEqual(use.organisation, church)
