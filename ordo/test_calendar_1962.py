from datetime import date

from django.test import SimpleTestCase, TestCase

from .calendar_1962 import (
    christ_the_king,
    ember_wednesday_of_september,
    first_sunday_of_advent,
    holy_family,
    holy_name,
    tempora_layout,
)
from .calendar_data import load_calendar_files
from .models import LiturgicalOccasion, occasion_for_date


def keys(day):
    return [o.key for o in occasion_for_date(day, "historic")]


class LayoutDateTests(SimpleTestCase):
    def test_the_dates_the_layout_is_worked_from(self):
        self.assertEqual(holy_family(2026), date(2026, 1, 11))
        self.assertEqual(first_sunday_of_advent(2026), date(2026, 11, 29))
        self.assertEqual(christ_the_king(2026), date(2026, 10, 25))
        # The Wednesday after the third Sunday of September.
        self.assertEqual(ember_wednesday_of_september(2026), date(2026, 9, 23))

    def test_holy_name_is_2_january_when_the_first_sunday_is_the_1st_6th_or_7th(self):
        self.assertEqual(holy_name(2026), date(2026, 1, 4))
        self.assertEqual(holy_name(2023), date(2023, 1, 2))  # 1 January was a Sunday

    def test_sundays_after_epiphany_left_out_are_resumed_in_november(self):
        # Easter 2024 was early (31 March), so Septuagesima cut the
        # Sundays after Epiphany short.
        layout = tempora_layout(2024)
        self.assertEqual(layout[date(2024, 11, 10)][0], ["tempora:Epi5-0"])
        self.assertEqual(layout[date(2024, 11, 17)][0], ["tempora:Epi6-0"])


class RulesOf1962Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        load_calendar_files()

    def test_the_immaculate_conception_is_kept_over_an_advent_sunday(self):
        # General Rubrics, 15: the Sunday is commemorated.
        self.assertEqual(keys(date(2024, 12, 8)), ["sancti:12-08", "tempora:Adv2-0"])

    def test_all_souls_moves_off_a_sunday_with_its_three_masses(self):
        self.assertEqual(keys(date(2025, 11, 2)), ["tempora:Pent21-0"])
        self.assertEqual(keys(date(2025, 11, 3)), ["sancti:11-02m1", "sancti:11-02m2", "sancti:11-02m3"])

    def test_the_vigil_of_christmas_replaces_the_fourth_sunday_of_advent(self):
        self.assertEqual(keys(date(2023, 12, 24)), ["sancti:12-24"])

    def test_holy_name_and_christ_the_king(self):
        self.assertEqual(keys(date(2026, 1, 4)), ["tempora:Nat2-0"])
        self.assertEqual(keys(date(2026, 10, 25)), ["sancti:10-DU"])

    def test_an_ember_day_keeps_a_commemoration_of_the_saint(self):
        self.assertEqual(keys(date(2026, 9, 23)), ["tempora:093-3", "sancti:09-23"])

    def test_a_second_class_sunday_commemorates_a_second_class_feast(self):
        # St Lawrence on the Ninth Sunday after Pentecost, 2025.
        self.assertEqual(keys(date(2025, 8, 10)), ["tempora:Pent09-0", "sancti:08-10"])

    def test_advent_weekdays_from_17_december_are_second_class(self):
        self.assertEqual(keys(date(2026, 12, 17)), ["tempora:Adv3-4"])

    def test_fourth_class_days_are_not_listed(self):
        # The Vigil of St Lawrence on a Saturday keeps only the Saturday
        # Office of Our Lady, a fourth-class day.
        self.assertEqual(keys(date(2025, 8, 9)), [])

    def test_the_ordinary_form_is_not_mixed_in(self):
        self.assertNotIn("nativity_of_the_lord", keys(date(2026, 12, 25)))
        self.assertIn("sancti:12-25m1", keys(date(2026, 12, 25)))

    def test_an_occasion_entered_by_hand_is_listed_last(self):
        LiturgicalOccasion.objects.create(
            name="Patronal festival", calendar_use="historic", fixed_month=10, fixed_day=25
        )
        self.assertEqual(keys(date(2026, 10, 25)), ["sancti:10-DU", ""])

    def test_a_1962_occasion_knows_its_date(self):
        septuagesima = LiturgicalOccasion.objects.get(calendar_use="historic", key="tempora:Quadp1-0")
        self.assertEqual(septuagesima.date_for_year(2026), date(2026, 2, 1))


class EnglandAndWales1962Tests(TestCase):
    """England's and Wales's 1962 days, checked against the Latin Mass
    Society's Ordo for 2025-26, from which they were taken."""

    @classmethod
    def setUpTestData(cls):
        load_calendar_files()

    def on(self, day, country):
        return [o.key for o in occasion_for_date(day, "historic", country)]

    def test_st_thomas_of_canterbury_is_first_class_in_both(self):
        for country in ("england", "wales"):
            with self.subTest(country=country):
                self.assertEqual(self.on(date(2025, 12, 29), country)[0], "sancti:12-29")
        self.assertNotEqual(keys(date(2025, 12, 29))[:1], ["sancti:12-29"])

    def test_st_george_is_first_class_in_england_and_third_in_wales(self):
        england = occasion_for_date(date(2026, 4, 23), "historic", "england")
        wales = occasion_for_date(date(2026, 4, 23), "historic", "wales")
        self.assertEqual([(o.key, o.rank) for o in england][:1], [("sancti:04-23", "class_1")])
        self.assertEqual([(o.key, o.rank) for o in wales][:1], [("sancti:04-23", "class_3")])
        self.assertEqual(keys(date(2026, 4, 23)), [])

    def test_st_david_moves_off_the_second_sunday_of_lent_in_wales(self):
        self.assertEqual(self.on(date(2026, 3, 1), "wales"), ["tempora:Quad2-0"])
        # With a commemoration of the Lent weekday, "at all Masses".
        self.assertEqual(self.on(date(2026, 3, 2), "wales"), ["sancti:03-01wa", "tempora:Quad2-1"])
        self.assertNotIn("sancti:03-01wa", self.on(date(2026, 3, 2), "england"))

    def test_a_national_saint_is_celebrated_and_the_universal_one_commemorated(self):
        self.assertEqual(self.on(date(2026, 5, 4), "england"), ["sancti:05-04ew", "sancti:05-04"])
        self.assertEqual(self.on(date(2026, 6, 22), "wales"), ["sancti:06-22ew", "sancti:06-22"])

    def test_fisher_and_more_and_st_edward(self):
        self.assertEqual(self.on(date(2026, 7, 9), "england"), ["sancti:07-09ew"])
        edward = occasion_for_date(date(2026, 10, 13), "historic", "england")
        self.assertEqual([(o.key, o.rank) for o in edward], [("sancti:10-13", "class_2")])

    def test_welsh_days_are_only_in_wales(self):
        for day, key in ((date(2026, 7, 17), "sancti:07-17wa"), (date(2026, 7, 30), "sancti:07-30wa"),
                         (date(2026, 8, 3), "sancti:08-03wa")):
            with self.subTest(key=key):
                self.assertEqual(self.on(day, "wales")[:1], [key])
                self.assertNotIn(key, self.on(day, "england"))

    def test_st_augustine_of_canterbury_moves_to_26_may(self):
        # 2025: second class, with St Philip Neri commemorated, and 28 May
        # is no longer his.
        self.assertEqual(self.on(date(2025, 5, 26), "england"), ["sancti:05-28", "sancti:05-26"])
        self.assertNotIn("sancti:05-28", self.on(date(2025, 5, 28), "england"))
        # 2024: 26 May was Trinity Sunday, which outranks him.
        self.assertEqual(self.on(date(2024, 5, 26), "england"), ["tempora:Pent01-0r"])
        # Universally he stays third class on 28 May.
        self.assertIn("sancti:05-28", keys(date(2024, 5, 28)))

    def test_st_brigid_and_st_cadoc_in_wales(self):
        self.assertEqual(self.on(date(2025, 2, 1), "wales"), ["sancti:02-01wa", "sancti:02-01"])
        self.assertEqual(self.on(date(2024, 9, 25), "wales")[:1], ["sancti:09-25wa"])
        self.assertNotIn("sancti:02-01wa", self.on(date(2025, 2, 1), "england"))

    def test_st_ubaldus_and_st_didacus_stay_commemorations(self):
        # Third class in the Ordo, but left as Missalemeum has them: no
        # bearing on planning music.
        self.assertEqual(self.on(date(2026, 5, 16), "england"), [])
        self.assertEqual(self.on(date(2026, 11, 13), "wales"), [])
