from datetime import date

from django.test import SimpleTestCase, TestCase

from .dates import NATIONAL_SETTINGS, YearDates, apply_transfers, rule_names
from .models import LiturgicalOccasion

GENERAL = NATIONAL_SETTINGS["general_roman"]
ENGLAND = NATIONAL_SETTINGS["england"]

# romcal's transfers for St Joseph and St George, converted.
OFF_A_SUNDAY = {"if_day_of_week": 0, "then": {"add_days": 1}}
OUT_OF_HOLY_WEEK_BEFORE = {
    "if_between": {"from": {"rule": "palm_sunday"}, "to": {"rule": "divine_mercy_sunday"}, "inclusive": True},
    "then": {"rule": "palm_sunday", "add_days": -1},
}
OUT_OF_HOLY_WEEK_AFTER = {
    "if_between": {"from": {"rule": "palm_sunday"}, "to": {"rule": "divine_mercy_sunday"}, "inclusive": True},
    "then": {"rule": "divine_mercy_sunday", "add_days": 1},
}


def rule(year, name, *args, settings=GENERAL, offset=0):
    return YearDates(year, settings).date_for(name, args, offset)


class RuleListTests(SimpleTestCase):
    def test_every_rule_the_ordinary_form_data_uses_exists(self):
        # romcal's date functions for the days in scope, in snake case.
        self.assertEqual(rule_names(), sorted([
            "all_saints", "annunciation", "ascension", "ash_wednesday", "assumption",
            "baptism_of_the_lord", "christmas", "corpus_christi", "date_of_ordinary_time",
            "divine_mercy_sunday", "easter_sunday", "epiphany", "exaltation_of_the_holy_cross",
            "good_friday", "holy_family", "holy_saturday", "holy_thursday",
            "immaculate_conception_of_mary", "immaculate_heart_of_mary", "mary_mother_of_god",
            "mary_mother_of_the_church", "most_sacred_heart_of_jesus", "nativity_of_john_the_baptist",
            "palm_sunday", "pentecost_sunday", "peter_and_paul_apostles", "presentation_of_the_lord",
            "privileged_weekday_of_advent", "second_sunday_after_christmas", "sunday_of_advent",
            "transfiguration", "trinity_sunday", "weekday_or_sunday_of_easter_time",
            "weekday_within_octave_of_christmas",
        ]))

    def test_an_unknown_rule_is_an_error(self):
        for name in ("christ_the_kingg", "date_for", "_easter"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                rule(2026, name)


class EasterRuleTests(SimpleTestCase):
    def test_days_counted_from_easter_2026(self):
        # Easter 2026 is 5 April.
        expected = {
            "ash_wednesday": date(2026, 2, 18),
            "palm_sunday": date(2026, 3, 29),
            "holy_thursday": date(2026, 4, 2),
            "good_friday": date(2026, 4, 3),
            "holy_saturday": date(2026, 4, 4),
            "easter_sunday": date(2026, 4, 5),
            "divine_mercy_sunday": date(2026, 4, 12),
            "ascension": date(2026, 5, 14),
            "pentecost_sunday": date(2026, 5, 24),
            "mary_mother_of_the_church": date(2026, 5, 25),
            "trinity_sunday": date(2026, 5, 31),
            "corpus_christi": date(2026, 6, 4),
            "most_sacred_heart_of_jesus": date(2026, 6, 12),
            "immaculate_heart_of_mary": date(2026, 6, 13),
        }
        for name, day in expected.items():
            with self.subTest(name=name):
                self.assertEqual(rule(2026, name), day)

    def test_england_keeps_corpus_christi_on_the_sunday(self):
        self.assertEqual(rule(2026, "corpus_christi", settings=ENGLAND), date(2026, 6, 7))
        self.assertEqual(rule(2026, "ascension", settings=ENGLAND), date(2026, 5, 14))

    def test_an_offset_counts_from_the_rule(self):
        # The Thursday after Ash Wednesday, and Easter Monday.
        self.assertEqual(rule(2026, "ash_wednesday", offset=1), date(2026, 2, 19))
        self.assertEqual(rule(2026, "easter_sunday", offset=1), date(2026, 4, 6))

    def test_easter_time_has_no_weekday_on_the_ascension(self):
        self.assertEqual(rule(2026, "weekday_or_sunday_of_easter_time", 0, 3), date(2026, 4, 19))
        self.assertIsNone(rule(2026, "weekday_or_sunday_of_easter_time", 4, 6))
        self.assertIsNone(rule(2026, "weekday_or_sunday_of_easter_time", 0, 8))


class AdventAndChristmasRuleTests(SimpleTestCase):
    def test_first_sunday_of_advent_for_each_weekday_of_christmas(self):
        cases = {
            2022: date(2022, 11, 27),  # Christmas on a Sunday
            2023: date(2023, 12, 3),   # Monday
            2024: date(2024, 12, 1),   # Wednesday
            2026: date(2026, 11, 29),  # Friday
            2027: date(2027, 11, 28),  # Saturday
        }
        for year, day in cases.items():
            with self.subTest(year=year):
                self.assertEqual(rule(year, "sunday_of_advent", 1), day)
        self.assertEqual(rule(2026, "sunday_of_advent", 4), date(2026, 12, 20))
        self.assertIsNone(rule(2026, "sunday_of_advent", 5))

    def test_privileged_advent_weekdays_skip_a_sunday(self):
        self.assertEqual(rule(2025, "privileged_weekday_of_advent", 22), date(2025, 12, 22))
        self.assertIsNone(rule(2025, "privileged_weekday_of_advent", 21))
        self.assertIsNone(rule(2025, "privileged_weekday_of_advent", 16))

    def test_holy_family(self):
        # The Sunday after Christmas, or 30 December when Christmas is a Sunday.
        self.assertEqual(rule(2026, "holy_family"), date(2026, 12, 27))
        self.assertEqual(rule(2022, "holy_family"), date(2022, 12, 30))

    def test_christmas_octave_has_no_weekday_on_holy_family(self):
        self.assertEqual(rule(2026, "weekday_within_octave_of_christmas", 2), date(2026, 12, 26))
        self.assertIsNone(rule(2026, "weekday_within_octave_of_christmas", 3))

    def test_immaculate_conception_leaves_an_advent_sunday(self):
        self.assertEqual(rule(2024, "immaculate_conception_of_mary"), date(2024, 12, 9))
        self.assertEqual(rule(2026, "immaculate_conception_of_mary"), date(2026, 12, 8))


class EpiphanyRuleTests(SimpleTestCase):
    def test_general_calendar_keeps_6_january(self):
        self.assertEqual(rule(2024, "epiphany"), date(2024, 1, 6))
        self.assertEqual(rule(2024, "baptism_of_the_lord"), date(2024, 1, 7))

    def test_england_moves_a_saturday_or_monday_epiphany_to_the_sunday(self):
        # 6 January 2024 was a Saturday; 2025, a Monday; 2026, a Tuesday.
        self.assertEqual(rule(2024, "epiphany", settings=ENGLAND), date(2024, 1, 7))
        self.assertEqual(rule(2025, "epiphany", settings=ENGLAND), date(2025, 1, 5))
        self.assertEqual(rule(2026, "epiphany", settings=ENGLAND), date(2026, 1, 6))

    def test_baptism_moves_to_monday_after_an_epiphany_on_7_january(self):
        self.assertEqual(rule(2024, "baptism_of_the_lord", settings=ENGLAND), date(2024, 1, 8))

    def test_second_sunday_after_christmas(self):
        self.assertEqual(rule(2026, "second_sunday_after_christmas"), date(2026, 1, 4))
        self.assertEqual(rule(2025, "second_sunday_after_christmas"), date(2025, 1, 5))
        # In England in 2025 that Sunday is Epiphany itself.
        self.assertIsNone(rule(2025, "second_sunday_after_christmas", settings=ENGLAND))

    def test_a_sunday_epiphany_calendar_has_no_second_sunday(self):
        from .dates import NationalSettings

        sunday_epiphany = NationalSettings(epiphany_on_sunday=True)
        self.assertEqual(rule(2026, "epiphany", settings=sunday_epiphany), date(2026, 1, 4))
        self.assertIsNone(rule(2026, "second_sunday_after_christmas", settings=sunday_epiphany))


class OrdinaryTimeRuleTests(SimpleTestCase):
    def test_sundays_before_lent_count_from_the_baptism(self):
        # The Baptism of the Lord in 2026 is Sunday 11 January.
        self.assertEqual(rule(2026, "date_of_ordinary_time", 0, 2), date(2026, 1, 18))
        self.assertEqual(rule(2026, "date_of_ordinary_time", 0, 5), date(2026, 2, 8))

    def test_sundays_after_pentecost_count_back_from_christ_the_king(self):
        # Christ the King is the 34th Sunday: the Sunday before Advent.
        self.assertEqual(rule(2026, "date_of_ordinary_time", 0, 34), date(2026, 11, 22))
        self.assertEqual(rule(2026, "date_of_ordinary_time", 0, 33), date(2026, 11, 15))

    def test_trinity_and_corpus_christi_take_their_sunday(self):
        # Trinity Sunday 2026 (31 May) would be a Sunday of Ordinary Time.
        weeks = YearDates(2026)._ordinary_time
        self.assertNotIn(date(2026, 5, 31), [d for days in weeks.values() for d in days.values()])
        england_weeks = YearDates(2026, ENGLAND)._ordinary_time
        self.assertNotIn(date(2026, 6, 7), [d for days in england_weeks.values() for d in days.values()])

    def test_a_week_that_does_not_occur_has_no_date(self):
        self.assertIsNone(rule(2026, "date_of_ordinary_time", 0, 40))


class FixedRuleTests(SimpleTestCase):
    def test_annunciation_leaves_holy_week_and_the_easter_octave(self):
        # 25 March 2024 was the Monday of Holy Week; Easter was 31 March.
        self.assertEqual(rule(2024, "annunciation"), date(2024, 4, 8))
        self.assertEqual(rule(2026, "annunciation"), date(2026, 3, 25))


class TransferTests(SimpleTestCase):
    def transfer(self, day, *transfers, settings=GENERAL):
        return apply_transfers(day, list(transfers), YearDates(day.year, settings))

    def test_st_joseph_leaves_a_sunday_and_holy_week(self):
        both = (OFF_A_SUNDAY, OUT_OF_HOLY_WEEK_BEFORE)
        # 2023: 19 March was a Sunday of Lent.
        self.assertEqual(self.transfer(date(2023, 3, 19), *both), date(2023, 3, 20))
        # 2035: the Monday of Holy Week, so the Saturday before Palm Sunday.
        self.assertEqual(self.transfer(date(2035, 3, 19), *both), date(2035, 3, 17))
        self.assertEqual(self.transfer(date(2026, 3, 19), *both), date(2026, 3, 19))

    def test_st_george_goes_to_the_monday_after_divine_mercy_sunday(self):
        # In 2025, 23 April was in the Easter Octave. The destination is the
        # rule's date plus a day (28 April); romcal adds the day to 23 April
        # instead, which leaves St George inside the octave.
        self.assertEqual(self.transfer(date(2025, 4, 23), OUT_OF_HOLY_WEEK_AFTER), date(2025, 4, 28))
        self.assertEqual(self.transfer(date(2026, 4, 23), OUT_OF_HOLY_WEEK_AFTER), date(2026, 4, 23))

    def test_conditions_test_the_original_date(self):
        # A Saturday moves forward and a Monday back (both to the Sunday),
        # without the second rule seeing the result of the first.
        saturday_forward = {"if_day_of_week": 6, "then": {"add_days": 1}}
        monday_back = {"if_day_of_week": 1, "then": {"add_days": -1}}
        self.assertEqual(self.transfer(date(2026, 6, 27), saturday_forward, monday_back), date(2026, 6, 28))
        self.assertEqual(self.transfer(date(2026, 6, 29), saturday_forward, monday_back), date(2026, 6, 28))

    def test_no_transfers_leaves_the_date(self):
        self.assertEqual(self.transfer(date(2026, 6, 29)), date(2026, 6, 29))


class OccasionDateTests(TestCase):
    def test_a_general_day_follows_the_chosen_national_calendar(self):
        corpus_christi = LiturgicalOccasion.objects.create(
            name="Corpus Christi", key="most_holy_body_and_blood_of_christ",
            date_rule="corpus_christi",
        )
        self.assertEqual(corpus_christi.date_for_year(2026), date(2026, 6, 4))
        self.assertEqual(corpus_christi.date_for_year(2026, "england"), date(2026, 6, 7))

    def test_rule_args_offset_and_transfers_come_from_the_row(self):
        fifth_sunday = LiturgicalOccasion.objects.create(
            name="Fifth Sunday in Ordinary Time", key="ordinary_time_5_sunday",
            date_rule="date_of_ordinary_time", date_rule_args=[0, 5],
        )
        easter_monday = LiturgicalOccasion.objects.create(
            name="Easter Monday", key="easter_monday", date_rule="easter_sunday", date_offset_days=1,
        )
        george = LiturgicalOccasion.objects.create(
            name="Saint George", key="george_of_lydda_martyr", calendar="england",
            fixed_month=4, fixed_day=23, transfers=[OUT_OF_HOLY_WEEK_AFTER],
        )
        self.assertEqual(fifth_sunday.date_for_year(2026), date(2026, 2, 8))
        self.assertEqual(easter_monday.date_for_year(2026), date(2026, 4, 6))
        self.assertEqual(george.date_for_year(2025), date(2025, 4, 28))

    def test_a_day_that_does_not_occur_has_no_date(self):
        ninth_week = LiturgicalOccasion.objects.create(
            name="40th Sunday", date_rule="date_of_ordinary_time", date_rule_args=[0, 40],
        )
        self.assertIsNone(ninth_week.date_for_year(2026))
