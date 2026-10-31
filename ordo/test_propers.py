import json
from datetime import date
from io import StringIO

from django.core.management import call_command
from django.db import IntegrityError
from django.test import TestCase

from .calendar_data import DATA_DIR, PROPERS_FILE, load_propers
from .models import LiturgicalOccasion, ProperChant, chant_season, proper_chants


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
    def test_loads_the_file_and_again_without_doubling(self):
        count = load_propers()
        self.assertGreater(count, 4000)
        self.assertEqual(load_propers(), count)
        self.assertEqual(ProperChant.objects.count(), count)

    def test_a_days_chants_come_through(self):
        load_propers()
        advent = ProperChant.objects.filter(occasion_key="tempora:Adv1-0")
        self.assertEqual(advent.get(part="introit").incipit, "Ad te levavi animam meam")
        self.assertEqual(advent.get(part="communion").source, "Divinum Officium Tempora/Adv1-0")

    def test_every_chant_belongs_to_a_1962_day(self):
        keys = set()
        for name in ("missalemeum/general_1962.json", "lms/england_1962.json", "lms/wales_1962.json"):
            keys |= {o["key"] for o in json.loads((DATA_DIR / name).read_text(encoding="utf-8"))["occasions"]}
        chants = json.loads(PROPERS_FILE.read_text(encoding="utf-8"))["chants"]
        self.assertEqual({row["key"] for row in chants} - keys, set())

    def test_the_calendar_command_loads_them(self):
        out = StringIO()
        call_command("load_calendar", stdout=out)
        self.assertIn(f"proper chants (1962): {ProperChant.objects.count()}", out.getvalue())


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
            "introit": "Gaudens gaudebo", "gradual": "Benedicta es tu", "alleluia": "Tota pulchra es",
        })

    def test_in_lent_the_tract_takes_the_alleluias_place(self):
        chants = proper_chants(self.immaculate, date(2027, 3, 1))
        self.assertEqual(chants["tract"], "Fundamenta ejus")
        self.assertNotIn("alleluia", chants)

    def test_in_eastertide_the_seasons_form_wins(self):
        self.assertEqual(proper_chants(self.immaculate, date(2027, 4, 10))["gradual"], "Tu gloria Jerusalem")

    def test_nothing_for_the_ordinary_form_or_no_occasion(self):
        ordinary_form = LiturgicalOccasion(key="immaculate_conception", calendar_use="current")
        self.assertEqual(proper_chants(ordinary_form, date(2026, 12, 8)), {})
        self.assertEqual(proper_chants(None, date(2026, 12, 8)), {})
