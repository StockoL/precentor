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
        self.assertEqual(
            set(counts),
            {"general_roman", "england", "wales", "general_roman (1962)", "england (1962)", "wales (1962)"},
        )
        self.assertEqual(counts["general_roman"], (223, 0))
        self.assertEqual(counts["general_roman (1962)"], (702, 0))
        self.assertEqual(LiturgicalOccasion.objects.filter(calendar_use="current", calendar="general_roman").count(), 223)

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


class ListableOccasionTests(TestCase):
    """The occasions a conductor can choose from, for one national calendar."""

    @classmethod
    def setUpTestData(cls):
        load_calendar_files()

    def keys(self, national_calendar, keep=()):
        return {(o.calendar_use, o.calendar, o.key) for o in LiturgicalOccasion.objects.listable(national_calendar, keep)}

    def test_both_forms_of_the_general_calendar(self):
        listed = self.keys("general_roman")
        self.assertIn(("current", "general_roman", "nativity_of_the_lord"), listed)
        self.assertIn(("historic", "general_roman", "sancti:12-25m1"), listed)

    def test_fourth_class_days_and_other_countries_are_left_out(self):
        listed = self.keys("england")
        self.assertFalse([k for k in listed if k[1] == "wales"])
        fourth_class = LiturgicalOccasion.objects.filter(calendar_use="historic", rank="class_4").values_list("key", flat=True)
        self.assertFalse({("historic", "general_roman", k) for k in fourth_class} & listed)

    def test_a_national_row_takes_the_general_rows_place(self):
        listed = self.keys("england")
        self.assertIn(("current", "england", "peter_and_paul_apostles"), listed)
        self.assertNotIn(("current", "general_roman", "peter_and_paul_apostles"), listed)
        self.assertIn(("historic", "england", "sancti:04-23"), listed)

    def test_a_memorial_england_makes_optional_is_not_listed_there(self):
        self.assertIn(("current", "general_roman", "elizabeth_of_hungary_religious"), self.keys("general_roman"))
        self.assertFalse([k for k in self.keys("england") if k[2] == "elizabeth_of_hungary_religious"])

    def test_occasions_entered_by_hand_are_listed(self):
        own = LiturgicalOccasion.objects.create(name="Patronal festival", fixed_month=8, fixed_day=9)
        self.assertIn(own, LiturgicalOccasion.objects.listable("england"))

    def test_an_occasion_already_chosen_stays_listed(self):
        welsh = LiturgicalOccasion.objects.get(calendar="wales", key="sancti:03-01wa")
        self.assertNotIn(welsh, LiturgicalOccasion.objects.listable("england"))
        self.assertIn(welsh, LiturgicalOccasion.objects.listable("england", keep=[welsh.pk, None]))

    def test_1962_days_are_labelled(self):
        george = LiturgicalOccasion.objects.get(calendar="england", key="sancti:04-23")
        self.assertEqual(george.choice_label, "St. George, Martyr, Patron of England (1962)")
        christmas = LiturgicalOccasion.objects.get(calendar_use="current", key="nativity_of_the_lord")
        self.assertEqual(christmas.choice_label, christmas.name)


class OccasionLookupNationalCalendarTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        load_calendar_files()

    def setUp(self):
        from django.contrib.auth import get_user_model

        self.client.force_login(get_user_model().objects.create_user(username="conductor", password="x"))

    def names(self, **params):
        response = self.client.get("/ordo/occasion-lookup/", {"date": "2026-04-23", "calendar_use": "current", **params})
        return [o["name"] for o in response.json()["occasions"]]

    def test_the_national_calendar_is_used(self):
        self.assertEqual(self.names(national_calendar="england"), ["Saint George, Martyr, Patron of England"])
        self.assertEqual(self.names(national_calendar="general_roman"), [])

    def test_an_unknown_or_missing_calendar_means_the_general_one(self):
        self.assertEqual(self.names(national_calendar="narnia"), [])
        self.assertEqual(self.names(), [])
