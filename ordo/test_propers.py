from django.db import IntegrityError
from django.test import TestCase

from .models import ProperChant


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
