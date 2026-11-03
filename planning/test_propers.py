from datetime import date

from django.test import TestCase

from ordo.models import LiturgicalOccasion, ProperChant
from accounts.testing import make_user
from precentor_project.testing import make_term

from .models import RolePiece, Service, ServiceRole


def chant(key, part, incipit, season="", position=0):
    ProperChant.objects.create(
        occasion_key=key, calendar_use="historic", part=part, season=season, incipit=incipit, source="test",
        position=position,
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
        self.assertEqual(self.slot("Introit").proper_suggestions, ["Gaudens gaudebo in Domino"])

    def test_alleluia_or_tract_takes_whichever_the_date_has(self):
        self.assertEqual(self.slot("Alleluia or Tract").proper_suggestions, ["Tota pulchra es"])

    def test_not_once_it_is_proposed(self):
        introit = self.slot("Introit")
        RolePiece.objects.create(service_role=introit, reference="Gaudens gaudebo in Domino")
        self.assertEqual(ServiceRole.objects.get(pk=introit.pk).proper_suggestions, [])

    def test_not_on_other_slots_or_without_data(self):
        self.assertEqual(self.slot("Kyrie").proper_suggestions, [])
        self.assertEqual(self.slot("Offertory").proper_suggestions, [])  # no Offertory loaded here
        # An Ordinary Form day sharing the key doesn't get the 1962 day's chants.
        self.service.occasion = LiturgicalOccasion.objects.create(
            name="Immaculate Conception", key="sancti:12-08", calendar_use="current"
        )
        self.service.save()
        service = Service.objects.get(pk=self.service.pk)
        self.assertEqual(ServiceRole.objects.create(service=service, role_name="Introit").proper_suggestions, [])


class SeveralChantsTests(ChantDayTestCase):
    """A day with three antiphons, as Palm Sunday has: each Antiphon slot
    is offered those no Antiphon slot has yet."""

    def setUp(self):
        super().setUp()
        for position, incipit in enumerate(["Hosanna filio David", "Pueri portantes", "Pueri vestimenta"]):
            chant("sancti:12-08", "antiphon", incipit, position=position)

    def test_each_antiphon_slot_is_offered_what_the_others_havent_taken(self):
        first = self.slot("Procession antiphon")
        self.assertEqual(first.proper_suggestions, ["Hosanna filio David", "Pueri portantes", "Pueri vestimenta"])
        RolePiece.objects.create(service_role=first, reference="Hosanna filio David")
        second = ServiceRole.objects.get(pk=self.slot("Second antiphon").pk)
        self.assertEqual(second.proper_suggestions, ["Pueri portantes", "Pueri vestimenta"])

    def test_the_same_words_in_another_part_are_still_offered(self):
        introit = self.slot("Introit")
        RolePiece.objects.create(service_role=introit, reference="Tota pulchra es")  # the Alleluia's words
        alleluia = ServiceRole.objects.get(pk=self.slot("Alleluia or Tract").pk)
        self.assertEqual(alleluia.proper_suggestions, ["Tota pulchra es"])


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


class SequenceSlotTests(TestCase):
    def test_a_sequence_slot_is_offered_the_days_sequence(self):
        from ordo.calendar_data import load_propers

        load_propers()
        easter = LiturgicalOccasion.objects.create(name="Easter Sunday", key="easter_sunday", calendar_use="current")
        term = make_term(start_date=date(2027, 3, 1), end_date=date(2027, 4, 30))
        service = Service.objects.create(term=term, date=date(2027, 3, 28), service_type="Sung Mass", occasion=easter)
        slot = ServiceRole.objects.create(service=service, role_name="Sequence")
        self.assertEqual((slot.kind, slot.proper_part), ("proper", "sequence"))
        self.assertEqual(slot.proper_suggestions, ["Victimae paschali laudes"])


class HolyWeekSlotTests(TestCase):
    """From the loaded data: the Easter Vigil's Alleluia or Tract slot and
    its Canticle slots, and Palm Sunday's antiphons."""

    def setUp(self):
        from ordo.calendar_data import load_propers

        load_propers()
        self.term = make_term(start_date=date(2027, 3, 1), end_date=date(2027, 4, 30))

    def service(self, key, day):
        occasion = LiturgicalOccasion.objects.create(name=key, key=key, calendar_use="current")
        return Service.objects.create(term=self.term, date=day, service_type="Liturgy", occasion=occasion)

    def test_the_vigils_tracts_then_its_alleluia(self):
        vigil = self.service("holy_saturday", date(2027, 3, 27))
        slot = ServiceRole.objects.create(service=vigil, role_name="Alleluia or Tract")
        self.assertEqual(slot.proper_suggestions, ["Iubilate Domino", "Qui confidunt", "Confitemini Domino"])
        canticle = ServiceRole.objects.create(service=vigil, role_name="Canticle", kind="canticle")
        self.assertEqual(canticle.proper_suggestions[0], "Cantemus Domino")
        self.assertEqual(len(canticle.proper_suggestions), 5)

    def test_palm_sundays_antiphons_in_order(self):
        palm = self.service("palm_sunday_of_the_passion_of_the_lord", date(2027, 3, 21))
        slot = ServiceRole.objects.create(service=palm, role_name="Procession antiphon")
        self.assertEqual(slot.proper_suggestions,
                         ["Hosanna filio David", "Pueri Hebraeorum, portantes", "Pueri Hebraeorum, vestimenta"])
