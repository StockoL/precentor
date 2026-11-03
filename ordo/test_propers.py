import json
from datetime import date
from io import StringIO

from django.core.management import call_command
from django.db import IntegrityError
from django.test import TestCase

from .calendar_data import DATA_DIR, PROPER_FILES, load_propers
from .models import LiturgicalOccasion, ProperChant, chant_season, proper_chants, weekday_sunday


def make_chant(**fields):
    defaults = {
        "occasion_key": "tempora:Adv1-0", "calendar_use": "historic", "part": "introit",
        "incipit": "Ad te levavi", "source": "Divinum Officium Tempora/Adv1-0",
    }
    return ProperChant.objects.create(**{**defaults, **fields})


class ProperChantTests(TestCase):
    def test_reads_as_its_part_and_name(self):
        self.assertEqual(str(make_chant()), "Introit: Ad te levavi")

    def test_one_chant_per_part_of_a_day(self):
        make_chant()
        with self.assertRaises(IntegrityError):
            make_chant(incipit="Something else")

    def test_a_seasonal_form_sits_beside_the_usual_one(self):
        make_chant(occasion_key="sancti:12-08", part="alleluia", incipit="Tota pulchra es")
        make_chant(occasion_key="sancti:12-08", part="alleluia", season="paschaltide", incipit="Tu gloria")
        self.assertEqual(ProperChant.objects.filter(occasion_key="sancti:12-08").count(), 2)


class LoadingPropersTests(TestCase):
    def test_loads_both_forms_and_again_without_doubling(self):
        counts = load_propers()
        self.assertGreater(counts["historic"], 4000)
        self.assertGreater(counts["current"], 400)
        self.assertEqual(load_propers(), counts)
        self.assertEqual(ProperChant.objects.count(), counts["historic"] + counts["current"])

    def test_a_days_chants_come_through(self):
        load_propers()
        advent = ProperChant.objects.filter(occasion_key="tempora:Adv1-0")
        self.assertEqual(advent.get(part="introit").incipit, "Ad te levavi animam meam")
        self.assertEqual(advent.get(part="communion").source, "Divinum Officium Tempora/Adv1-0")
        now = ProperChant.objects.filter(calendar_use="current", occasion_key="advent_1_sunday")
        self.assertEqual(now.get(part="introit").incipit, "Ad te levavi")
        self.assertEqual(now.get(part="introit").source, "Graduale Romanum (1974), First Sunday of Advent")
        holy_family = ProperChant.objects.filter(occasion_key="holy_family_of_jesus_mary_and_joseph")
        self.assertEqual(holy_family.get(part="communion", cycle="A").incipit, "Tolle puerum")

    def test_every_chant_belongs_to_a_day_of_its_form(self):
        days = {
            "historic": ("missalemeum/general_1962.json", "lms/england_1962.json", "lms/wales_1962.json"),
            "current": ("romcal/general_roman.json", "romcal/england.json", "romcal/wales.json"),
        }
        for path, calendar_use, _ in PROPER_FILES:
            keys = set()
            for name in days[calendar_use]:
                keys |= {o["key"] for o in json.loads((DATA_DIR / name).read_text(encoding="utf-8"))["occasions"]}
            chants = json.loads(path.read_text(encoding="utf-8"))["chants"]
            with self.subTest(form=calendar_use):
                self.assertEqual({row["key"] for row in chants} - keys, set())

    def test_the_calendar_command_loads_them(self):
        out = StringIO()
        call_command("load_calendar", stdout=out)
        historic = ProperChant.objects.filter(calendar_use="historic").count()
        current = ProperChant.objects.filter(calendar_use="current").count()
        self.assertIn(f"proper chants: {historic} for 1962, {current} for the Ordinary Form", out.getvalue())


class ChoosingChantsTests(TestCase):
    """In 2027 Easter is on 28 March, so Septuagesima is 24 January and
    Eastertide ends on 22 May."""

    def setUp(self):
        self.immaculate = LiturgicalOccasion(key="sancti:12-08", calendar_use="historic")
        for part, season, incipit in [
            ("introit", "", "Gaudens gaudebo"), ("gradual", "", "Benedicta es tu"),
            ("alleluia", "", "Tota pulchra es"), ("tract", "septuagesima", "Fundamenta ejus"),
            ("gradual", "paschaltide", "Tu gloria Jerusalem"),
        ]:
            make_chant(occasion_key="sancti:12-08", part=part, season=season, incipit=incipit)

    def test_the_seasons_edges(self):
        self.assertEqual(chant_season(date(2027, 1, 23)), "")
        self.assertEqual(chant_season(date(2027, 1, 24)), "septuagesima")
        self.assertEqual(chant_season(date(2027, 3, 27)), "septuagesima")
        self.assertEqual(chant_season(date(2027, 3, 28)), "paschaltide")
        self.assertEqual(chant_season(date(2027, 5, 22)), "paschaltide")
        self.assertEqual(chant_season(date(2027, 5, 23)), "")

    def test_the_usual_chants(self):
        self.assertEqual(proper_chants(self.immaculate, date(2026, 12, 8)), {
            "introit": ["Gaudens gaudebo"], "gradual": ["Benedicta es tu"], "alleluia": ["Tota pulchra es"],
        })

    def test_in_lent_the_tract_takes_the_alleluias_place(self):
        chants = proper_chants(self.immaculate, date(2027, 3, 1))
        self.assertEqual(chants["tract"], ["Fundamenta ejus"])
        self.assertNotIn("alleluia", chants)

    def test_in_eastertide_the_seasons_form_wins(self):
        self.assertEqual(proper_chants(self.immaculate, date(2027, 4, 10))["gradual"], ["Tu gloria Jerusalem"])

    def test_nothing_for_the_ordinary_form_or_no_occasion(self):
        ordinary_form = LiturgicalOccasion(key="immaculate_conception", calendar_use="current")
        self.assertEqual(proper_chants(ordinary_form, date(2026, 12, 8)), {})
        self.assertEqual(proper_chants(None, date(2026, 12, 8)), {})


class OrdinaryFormChantTests(TestCase):
    """The Tenth Sunday in Ordinary Time has one Communion for Years A and
    C and another for Year B. 14 June 2026 is in Year A, 13 June 2027 in
    Year B."""

    def setUp(self):
        self.sunday = LiturgicalOccasion(key="ordinary_time_10_sunday", calendar_use="current")
        for part, cycle, incipit in [("introit", "", "Dominus illuminatio mea"),
                                     ("communion", "", "Dominus firmamentum meum"),
                                     ("communion", "B", "Quicumque fecerit")]:
            make_chant(occasion_key="ordinary_time_10_sunday", calendar_use="current", part=part, cycle=cycle,
                       incipit=incipit)

    def test_the_usual_chant_in_other_years(self):
        self.assertEqual(proper_chants(self.sunday, date(2026, 6, 14)), {
            "introit": ["Dominus illuminatio mea"], "communion": ["Dominus firmamentum meum"],
        })

    def test_the_years_own_chant_wins(self):
        self.assertEqual(proper_chants(self.sunday, date(2027, 6, 13))["communion"], ["Quicumque fecerit"])

    def test_the_two_forms_never_mix(self):
        make_chant(occasion_key="ordinary_time_10_sunday", part="offertory", incipit="Not this form")
        self.assertNotIn("offertory", proper_chants(self.sunday, date(2026, 6, 14)))

    def test_the_loaded_data_gives_each_year_its_own_communion_in_lent(self):
        load_propers()
        lent_5 = LiturgicalOccasion(key="lent_5_sunday", calendar_use="current")
        self.assertEqual(proper_chants(lent_5, date(2026, 3, 22))["communion"], ["Videns Dominus"])  # Year A
        self.assertEqual(proper_chants(lent_5, date(2027, 3, 14))["communion"], ["Qui mihi ministrat"])  # Year B

    def test_each_christmas_mass_has_its_own_chants(self):
        load_propers()
        introits = {
            "nativity_of_the_lord_vigil_mass": "Hodie scietis",
            "nativity_of_the_lord_mass_during_the_night": "Dominus dixit",
            "nativity_of_the_lord_mass_at_dawn": "Lux fulgebit",
            "nativity_of_the_lord": "Puer natus est nobis",
        }
        for key, introit in introits.items():
            mass = LiturgicalOccasion(key=key, calendar_use="current")
            with self.subTest(mass=key):
                self.assertEqual(proper_chants(mass, date(2026, 12, 25))["introit"], [introit])

    def test_several_chants_of_one_part_come_in_the_order_sung(self):
        for position, incipit in [(2, "Pueri Hebraeorum, vestimenta"), (0, "Hosanna filio David"),
                                  (1, "Pueri Hebraeorum, portantes")]:
            make_chant(occasion_key="palm_sunday", calendar_use="current", part="antiphon", position=position,
                       incipit=incipit)
        palm_sunday = LiturgicalOccasion(key="palm_sunday", calendar_use="current")
        self.assertEqual(proper_chants(palm_sunday, date(2027, 3, 21))["antiphon"], [
            "Hosanna filio David", "Pueri Hebraeorum, portantes", "Pueri Hebraeorum, vestimenta",
        ])


class WeekdaySundayTests(TestCase):
    """Which Sunday's propers an Ordinary Form weekday sings, from the
    loaded calendar. Advent 2026 starts on 29 November; Easter 2027 is on
    28 March, with Ash Wednesday on 10 February."""

    @classmethod
    def setUpTestData(cls):
        call_command("load_calendar", stdout=StringIO())

    def key(self, day):
        sunday = weekday_sunday(day)
        return sunday.key if sunday else None

    def test_a_weekday_takes_the_sunday_before(self):
        self.assertEqual(self.key(date(2027, 2, 9)), "ordinary_time_5_sunday")
        self.assertEqual(self.key(date(2026, 12, 12)), "advent_2_sunday")
        self.assertEqual(self.key(date(2027, 4, 6)), "divine_mercy_sunday")

    def test_none_for_days_with_masses_of_their_own(self):
        for day in [date(2026, 12, 17), date(2026, 12, 29), date(2027, 3, 2), date(2027, 3, 31)]:
            with self.subTest(day=day):
                self.assertIsNone(self.key(day))  # late Advent, Christmas, Lent, the Easter octave

    def test_none_on_a_sunday(self):
        self.assertIsNone(self.key(date(2027, 2, 7)))
