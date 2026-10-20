from datetime import date
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from .calendar_data import load_calendar_files
from .models import LiturgicalOccasion, occasion_for_date


def names(day, national_calendar="general_roman"):
    return [o.name for o in occasion_for_date(day, "current", national_calendar)]


class LoadingTests(TestCase):
    def test_loads_each_calendar_and_reports_the_counts(self):
        counts = load_calendar_files()
        self.assertEqual(set(counts), {"general_roman", "england", "wales"})
        self.assertEqual(counts["general_roman"], (223, 0))
        self.assertEqual(LiturgicalOccasion.objects.filter(calendar="general_roman").count(), 223)

    def test_loading_again_updates_and_adds_nothing(self):
        load_calendar_files()
        total = LiturgicalOccasion.objects.count()
        counts = load_calendar_files()
        self.assertEqual(LiturgicalOccasion.objects.count(), total)
        self.assertEqual(counts["general_roman"], (0, 223))

    def test_an_edited_row_is_restored_and_a_conductors_own_is_left_alone(self):
        load_calendar_files()
        christmas = LiturgicalOccasion.objects.get(key="nativity_of_the_lord", calendar="general_roman")
        christmas.colour = "green"
        christmas.save()
        own = LiturgicalOccasion.objects.create(name="Patronal festival", fixed_month=8, fixed_day=9)
        load_calendar_files()
        christmas.refresh_from_db()
        self.assertEqual(christmas.colour, "white")
        self.assertTrue(LiturgicalOccasion.objects.filter(pk=own.pk).exists())

    def test_rules_seasons_and_colours_come_through(self):
        load_calendar_files()
        sunday = LiturgicalOccasion.objects.get(key="ordinary_time_5_sunday")
        self.assertEqual(sunday.name, "Fifth Sunday in Ordinary Time")
        self.assertEqual((sunday.date_rule, sunday.date_rule_args), ("date_of_ordinary_time", [0, 5]))
        self.assertEqual((sunday.colour, sunday.season.name), ("green", "Ordinary Time"))
        self.assertEqual(LiturgicalOccasion.objects.get(key="advent_3_sunday").colour, "rose")
        # A saint's day falls in different seasons in different years.
        self.assertIsNone(LiturgicalOccasion.objects.get(key="andrew_apostle", calendar="general_roman").season)

    def test_the_command_loads_the_files(self):
        out = StringIO()
        call_command("load_calendar", stdout=out)
        self.assertIn("general_roman: 223 added, 0 updated", out.getvalue())


class RealCalendarTests(TestCase):
    """A few days of 2026, end to end, with the published data loaded."""

    @classmethod
    def setUpTestData(cls):
        load_calendar_files()

    def test_sundays_and_solemnities(self):
        self.assertEqual(names(date(2026, 2, 8)), ["Fifth Sunday in Ordinary Time"])
        self.assertEqual(names(date(2026, 12, 25)), ["The Nativity of the Lord (Christmas)"])

    def test_corpus_christi_moves_to_the_sunday_in_england(self):
        self.assertEqual(names(date(2026, 6, 4)), ["The Most Holy Body and Blood of Christ"])
        self.assertEqual(names(date(2026, 6, 4), "england"), [])
        self.assertEqual(names(date(2026, 6, 7), "england"), ["The Most Holy Body and Blood of Christ"])

    def test_st_george_is_a_solemnity_only_in_england(self):
        self.assertEqual(names(date(2026, 4, 23)), [])
        self.assertEqual(names(date(2026, 4, 23), "england"), ["Saint George, Martyr, Patron of England"])

    def test_england_makes_st_elizabeth_optional(self):
        # An obligatory memorial in the general calendar, optional in
        # England, and Precentor leaves optional memorials out.
        self.assertEqual(names(date(2026, 11, 17)), ["Saint Elizabeth of Hungary, Religious"])
        self.assertEqual(names(date(2026, 11, 17), "england"), [])

    def test_a_memorial_in_lent_is_kept_alongside_the_weekday(self):
        # SS Perpetua and Felicity, 7 March 2026, a Saturday of Lent.
        self.assertEqual(
            names(date(2026, 3, 7)),
            ["Saturday of the Second Week of Lent", "Saints Perpetua and Felicity, Martyrs"],
        )
