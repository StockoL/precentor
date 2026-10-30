from datetime import date

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from accounts.testing import make_user
from precentor_project.testing import make_score, make_term

from .models import RolePiece, Service, ServiceRole


class ReferencePieceTestMixin:
    def setUp(self):
        self.conductor = make_user("conductor")
        self.church = self.conductor.organisation
        term = make_term(organisation=self.church)
        self.service = Service.objects.create(term=term, date=date(2026, 1, 11), service_type="Sung Mass")
        self.slot = ServiceRole.objects.create(service=self.service, role_name="Entrance hymn")
        self.score = make_score(organisation=self.church, title="Ave verum corpus", composer_surname="Byrd")


class ScoreOrReferenceTests(ReferencePieceTestMixin, TestCase):
    def test_a_reference_is_a_piece_of_its_own(self):
        piece = RolePiece.objects.create(service_role=self.slot, reference="  NEH 123 ")
        self.assertEqual((piece.score, piece.reference, piece.title), (None, "NEH 123", "NEH 123"))

    def test_a_score_is_titled_as_the_score(self):
        piece = RolePiece.objects.create(service_role=self.slot, score=self.score)
        self.assertEqual(piece.title, str(self.score))

    def test_the_database_refuses_neither_or_both(self):
        for fields in ({}, {"score": self.score, "reference": "NEH 123"}):
            with self.subTest(fields=fields), self.assertRaises(IntegrityError), transaction.atomic():
                RolePiece.objects.create(service_role=self.slot, **fields)

    def test_the_rule_gives_its_message_before_the_database_is_asked(self):
        message = "Choose a score or type a reference, not both."
        for fields in ({}, {"score": self.score, "reference": "NEH 123"}):
            with self.subTest(fields=fields), self.assertRaisesMessage(ValidationError, message):
                RolePiece(service_role=self.slot, **fields).validate_constraints()
        RolePiece(service_role=self.slot, reference="NEH 123").validate_constraints()


class ReferenceShownTests(ReferencePieceTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.hymn = RolePiece.objects.create(service_role=self.slot, reference="NEH 123", is_confirmed=True)
        motet = ServiceRole.objects.create(service=self.service, role_name="Offertory motet")
        RolePiece.objects.create(service_role=motet, score=self.score, is_confirmed=True)
        self.client.force_login(self.conductor)

    def test_the_service_page_shows_the_reference(self):
        response = self.client.get(self.service.get_absolute_url())
        self.assertContains(response, "NEH 123")

    def test_the_music_list_gives_references_and_scores_alike(self):
        rows = self.service.music_list_rows()
        self.assertEqual([(row["role_name"], row["pieces"]) for row in rows], [
            ("Entrance hymn", ["NEH 123"]),
            ("Offertory motet", [str(self.score)]),
        ])
        response = self.client.get(f"/terms/{self.service.term.pk}/music-list/")
        self.assertContains(response, "NEH 123")

    def test_a_reference_piece_is_named_by_its_reference(self):
        self.assertEqual(str(self.hymn), "NEH 123 (confirmed)")


class ProposeReferenceTests(ReferencePieceTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.conductor)
        self.url = f"/roles/{self.slot.pk}/pieces/add/"

    def test_a_reference_can_be_proposed_without_javascript(self):
        response = self.client.post(self.url, {"score": "", "reference": "NEH 123"})
        self.assertRedirects(response, self.service.get_absolute_url())
        self.assertEqual(RolePiece.objects.get().title, "NEH 123")

    def test_neither_or_both_is_refused_with_one_message(self):
        for data in ({"score": "", "reference": ""}, {"score": self.score.pk, "reference": "NEH 123"}):
            with self.subTest(data=data):
                response = self.client.post(self.url, data)
                self.assertContains(response, "Choose a score or type a reference, not both.", count=1)
        self.assertFalse(RolePiece.objects.exists())

    def test_a_hymn_slot_asks_for_the_reference_first(self):
        form = self.client.get(self.url).context["form"]
        self.assertEqual(list(form.fields), ["reference", "score"])
        self.assertEqual(form.fields["score"].label, "Or a score from the library")

    def test_other_slots_ask_for_a_score_first(self):
        motet = ServiceRole.objects.create(service=self.service, role_name="Offertory motet")
        form = self.client.get(f"/roles/{motet.pk}/pieces/add/").context["form"]
        self.assertEqual(list(form.fields), ["score", "reference"])
        self.assertEqual(form.fields["reference"].label, "Or type a reference")
