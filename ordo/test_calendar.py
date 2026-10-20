from datetime import date

from django.test import TestCase

from .calendar import resolve_year
from .models import LiturgicalOccasion, occasion_for_date


def make(name, day, precedence, rank, key=None, proper_of_time=False, calendar="general_roman",
         shares=False):
    """An occasion on a fixed date, so a test is about precedence only."""
    return LiturgicalOccasion.objects.create(
        name=name, key=key or name.lower().replace(" ", "_"), calendar=calendar,
        fixed_month=day.month, fixed_day=day.day,
        precedence=precedence, rank=rank, is_proper_of_time=proper_of_time,
        shares_with_memorials=shares,
    )


def names(day, national_calendar="general_roman"):
    return [o.name for o in resolve_year(day.year, national_calendar=national_calendar).get(day, [])]


SUNDAY = date(2026, 8, 9)
LENT_WEEKDAY = date(2026, 3, 4)


class WhatWinsTests(TestCase):
    def test_a_sunday_in_ordinary_time_beats_a_saints_feast(self):
        make("Nineteenth Sunday", SUNDAY, "6", "sunday", proper_of_time=True)
        make("A feast", SUNDAY, "7", "feast")
        self.assertEqual(names(SUNDAY), ["Nineteenth Sunday"])

    def test_a_feast_of_the_lord_and_a_solemnity_beat_a_sunday_in_ordinary_time(self):
        make("Nineteenth Sunday", SUNDAY, "6", "sunday", proper_of_time=True)
        make("A feast of the Lord", SUNDAY, "5", "feast")
        self.assertEqual(names(SUNDAY), ["A feast of the Lord"])
        make("A solemnity", SUNDAY, "3", "solemnity")
        self.assertEqual(names(SUNDAY), ["A solemnity"])

    def test_a_memorial_on_a_sunday_is_left_out(self):
        make("Nineteenth Sunday", SUNDAY, "6", "sunday", proper_of_time=True)
        make("A memorial", SUNDAY, "10", "memorial")
        self.assertEqual(names(SUNDAY), ["Nineteenth Sunday"])

    def test_a_national_day_outranks_a_general_one_by_its_level(self):
        make("A memorial", SUNDAY, "10", "memorial")
        make("A national feast", SUNDAY, "8c", "feast")
        self.assertEqual(names(SUNDAY), ["A national feast"])


class KeptAlongsideTests(TestCase):
    def test_a_memorial_on_a_weekday_of_lent_is_still_kept(self):
        make("Wednesday of the Second Week of Lent", LENT_WEEKDAY, "9", "weekday", proper_of_time=True)
        make("A memorial", LENT_WEEKDAY, "10", "memorial")
        self.assertEqual(names(LENT_WEEKDAY), ["Wednesday of the Second Week of Lent", "A memorial"])

    def test_a_memorial_that_shares_keeps_the_other_memorial(self):
        # The Immaculate Heart of Mary and St Anthony, 13 June 2026.
        day = date(2026, 6, 13)
        make("Saint Anthony", day, "10", "memorial")
        make("Immaculate Heart of Mary", day, "10", "memorial", proper_of_time=True, shares=True)
        self.assertEqual(names(day), ["Immaculate Heart of Mary", "Saint Anthony"])

    def test_otherwise_the_first_of_two_memorials_prevails(self):
        # Mary, Mother of the Church and St Justin, 1 June 2020.
        day = date(2020, 6, 1)
        make("Saint Justin", day, "10", "memorial")
        make("Mary, Mother of the Church", day, "10", "memorial", proper_of_time=True)
        self.assertEqual(names(day), ["Mary, Mother of the Church"])

    def test_no_memorial_is_kept_in_holy_week(self):
        # 7 April 2020 was the Tuesday of Holy Week. romcal's data ranks
        # it as a privileged weekday, which on its own would keep the
        # memorial, so the check goes by the date.
        day = date(2020, 4, 7)
        make("Tuesday of Holy Week", day, "9", "weekday", proper_of_time=True)
        make("A memorial", day, "10", "memorial")
        self.assertEqual(names(day), ["Tuesday of Holy Week"])

    def test_holy_thursday_is_kept_with_the_lords_supper(self):
        day = date(2026, 4, 2)
        make("Thursday of Holy Week", day, "9", "weekday", proper_of_time=True)
        make("The Lord's Supper", day, "1", "solemnity", proper_of_time=True)
        self.assertEqual(names(day), ["The Lord's Supper", "Thursday of Holy Week"])


class ImpededSolemnityTests(TestCase):
    def setUp(self):
        # The Easter Octave 2026: 6 to 12 April, all of level 2.
        for offset in range(7):
            make(f"Octave day {offset}", date(2026, 4, 6 + offset), "2", "weekday", proper_of_time=True)

    def test_an_impeded_solemnity_moves_to_the_first_free_day(self):
        make("A solemnity", date(2026, 4, 8), "3", "solemnity")
        self.assertEqual(names(date(2026, 4, 8)), ["Octave day 2"])
        self.assertEqual(names(date(2026, 4, 13)), ["A solemnity"])

    def test_a_moved_solemnity_displaces_a_memorial(self):
        make("A solemnity", date(2026, 4, 8), "3", "solemnity")
        make("A memorial", date(2026, 4, 13), "10", "memorial")
        self.assertEqual(names(date(2026, 4, 13)), ["A solemnity"])

    def test_a_feast_that_is_impeded_does_not_move(self):
        make("A feast", date(2026, 4, 8), "7", "feast")
        self.assertEqual(names(date(2026, 4, 13)), [])

    def test_the_proper_of_time_wins_between_two_solemnities(self):
        # 2022: the Sacred Heart fell on the Nativity of John the Baptist.
        day = date(2022, 6, 24)
        make("Nativity of John the Baptist", day, "3", "solemnity")
        make("Sacred Heart", day, "3", "solemnity", proper_of_time=True)
        self.assertEqual(names(day), ["Sacred Heart"])
        self.assertEqual(names(date(2022, 6, 25)), ["Nativity of John the Baptist"])


class NationalCalendarTests(TestCase):
    def test_a_national_row_replaces_the_general_one_with_the_same_key(self):
        day = date(2026, 4, 23)
        make("Saint George (general)", day, "10", "memorial", key="george")
        make("Saint George (England)", day, "4a", "solemnity", key="george", calendar="england")
        self.assertEqual(names(day), ["Saint George (general)"])
        self.assertEqual(names(day, "england"), ["Saint George (England)"])

    def test_another_countrys_days_are_left_out(self):
        day = date(2026, 3, 1)
        make("Saint David", day, "3", "solemnity", key="david", calendar="wales")
        self.assertEqual(names(day, "england"), [])
        self.assertEqual(names(day, "wales"), ["Saint David"])


class OccasionsEnteredByHandTests(TestCase):
    def test_an_occasion_without_a_precedence_is_always_listed_last(self):
        make("Nineteenth Sunday", SUNDAY, "6", "sunday", proper_of_time=True)
        LiturgicalOccasion.objects.create(name="Patronal festival", fixed_month=8, fixed_day=9)
        self.assertEqual(names(SUNDAY), ["Nineteenth Sunday", "Patronal festival"])


class OccasionForDateTests(TestCase):
    def test_returns_the_resolved_day_or_an_empty_list(self):
        make("Nineteenth Sunday", SUNDAY, "6", "sunday", proper_of_time=True)
        make("A memorial", SUNDAY, "10", "memorial")
        self.assertEqual([o.name for o in occasion_for_date(SUNDAY, "current")], ["Nineteenth Sunday"])
        self.assertEqual(occasion_for_date(date(2026, 8, 10), "current"), [])

    def test_only_the_chosen_form_is_considered(self):
        make("Nineteenth Sunday", SUNDAY, "6", "sunday", proper_of_time=True)
        self.assertEqual(occasion_for_date(SUNDAY, "historic"), [])
