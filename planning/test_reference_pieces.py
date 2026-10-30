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

    def test_clean_says_so_before_the_database_does(self):
        for fields in ({"reference": "   "}, {"score": self.score, "reference": "NEH 123"}):
            with self.subTest(fields=fields), self.assertRaises(ValidationError):
                RolePiece(service_role=self.slot, **fields).clean()
        RolePiece(service_role=self.slot, reference="NEH 123").clean()

    def test_proposing_still_needs_a_score_for_now(self):
        self.client.force_login(self.conductor)
        self.client.post(f"/roles/{self.slot.pk}/pieces/add/", {"score": ""})
        self.assertFalse(RolePiece.objects.exists())


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
