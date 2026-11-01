from datetime import date

from django.test import TestCase

from ordo.models import LiturgicalOccasion, ProperChant
from accounts.testing import make_user
from precentor_project.testing import make_term

from .models import RolePiece, Service, ServiceRole


def chant(key, part, incipit, season=""):
    ProperChant.objects.create(
        occasion_key=key, calendar_use="historic", part=part, season=season, incipit=incipit, source="test"
    )


class ChantDayTestCase(TestCase):
    """A 1962 service on the Immaculate Conception, 8 December 2026,
    outside Lent and Eastertide, with some of its chants loaded."""

    def setUp(self):
        for part, incipit in [("introit", "Gaudens gaudebo in Domino"), ("alleluia", "Tota pulchra es")]:
            chant("sancti:12-08", part, incipit)
        chant("sancti:12-08", "tract", "Fundamenta ejus", season="septuagesima")
        self.feast = LiturgicalOccasion.objects.create(
            name="Immaculate Conception", key="sancti:12-08", calendar_use="historic"
        )
        term = make_term(start_date=date(2026, 11, 29), end_date=date(2026, 12, 24), calendar_use="historic")
        self.service = Service.objects.create(
            term=term, date=date(2026, 12, 8), service_type="Sung Mass", occasion=self.feast
        )

    def slot(self, name):
        return ServiceRole.objects.create(service=self.service, role_name=name)


class ProperSuggestionTests(ChantDayTestCase):
    """The day's chant offered on a Proper slot."""

    def test_a_proper_slot_is_offered_its_chant(self):
        self.assertEqual(self.slot("Introit").proper_suggestion, "Gaudens gaudebo in Domino")

    def test_alleluia_or_tract_takes_whichever_the_date_has(self):
        self.assertEqual(self.slot("Alleluia or Tract").proper_suggestion, "Tota pulchra es")

    def test_not_once_it_is_proposed(self):
        introit = self.slot("Introit")
        RolePiece.objects.create(service_role=introit, reference="Gaudens gaudebo in Domino")
        self.assertIsNone(ServiceRole.objects.get(pk=introit.pk).proper_suggestion)

    def test_not_on_other_slots_or_without_data(self):
        self.assertIsNone(self.slot("Kyrie").proper_suggestion)
        self.assertIsNone(self.slot("Offertory").proper_suggestion)  # no Offertory loaded here
        # An Ordinary Form day sharing the key doesn't get the 1962 day's chants.
        self.service.occasion = LiturgicalOccasion.objects.create(
            name="Immaculate Conception", key="sancti:12-08", calendar_use="current"
        )
        self.service.save()
        service = Service.objects.get(pk=self.service.pk)
        self.assertIsNone(ServiceRole.objects.create(service=service, role_name="Introit").proper_suggestion)


class ProposePageChantTests(ChantDayTestCase):
    """The propose page, which works without JavaScript, offers the chant
    as a form of its own."""

    def setUp(self):
        super().setUp()
        self.client.force_login(make_user("conductor", organisation=self.service.organisation))

    def test_the_page_offers_the_chant_and_it_can_be_proposed(self):
        introit = self.slot("Introit")
        response = self.client.get(f"/roles/{introit.pk}/pieces/add/")
        self.assertContains(response, "Propose Gaudens gaudebo in Domino")
        self.client.post(f"/roles/{introit.pk}/pieces/add/", {"reference": "Gaudens gaudebo in Domino"})
        self.assertEqual(RolePiece.objects.get(service_role=introit).reference, "Gaudens gaudebo in Domino")
        self.assertNotContains(self.client.get(f"/roles/{introit.pk}/pieces/add/"), "For this day")
