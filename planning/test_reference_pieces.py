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
        self.assertEqual([(row["role_name"], row["kind"], row["proper_part"], row["pieces"]) for row in rows], [
            ("Entrance hymn", "hymn", "", ["NEH 123"]),
            ("Offertory motet", "motet", "", [str(self.score)]),
        ])
        response = self.client.get(f"/terms/{self.service.term.pk}/music-list/")
        self.assertContains(response, "NEH 123")
        self.assertContains(response, '<dt data-kind="hymn">Entrance hymn</dt>', html=True)

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


class HymnsAndPsalmIntoSlotsTests(ReferencePieceTestMixin, TestCase):
    def run_migration(self):
        import importlib

        from django.apps import apps

        importlib.import_module("planning.migrations.0023_hymns_and_psalm_into_slots").copy_into_slots(apps, None)

    def pieces(self, service):
        return [
            (piece.service_role.role_name, piece.service_role.kind, piece.reference, piece.is_confirmed)
            for piece in RolePiece.objects.filter(service_role__service=service).order_by("service_role__position", "id")
        ]

    def test_hymns_become_one_slot_and_the_psalm_another(self):
        self.service.hymns = "NEH 1, NEH 33,, NEH 271 "
        self.service.psalm = "150"
        self.service.save()
        self.run_migration()
        self.assertEqual(self.pieces(self.service), [
            ("Hymns", "hymn", "NEH 1", True),
            ("Hymns", "hymn", "NEH 33", True),
            ("Hymns", "hymn", "NEH 271", True),
            ("Psalm", "psalm", "150", True),
        ])
        hymns = self.service.roles.get(role_name="Hymns")
        self.assertEqual((hymns.organisation, hymns.position), (self.church, 2))

    def test_a_slot_already_named_psalm_takes_the_piece(self):
        psalm = ServiceRole.objects.create(service=self.service, role_name="psalm")
        self.service.psalm = "Psalm 24"
        self.service.save()
        self.run_migration()
        self.assertEqual(list(psalm.pieces.values_list("reference", flat=True)), ["Psalm 24"])
        self.assertEqual(self.service.roles.count(), 2)

    def test_a_service_with_neither_is_left_alone(self):
        self.run_migration()
        self.assertEqual(list(self.service.roles.values_list("role_name", flat=True)), ["Entrance hymn"])


class MusicListArrangementTests(ReferencePieceTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        for name, reference in (("Introit", "Ad te levavi"), ("Kyrie", "Missa de Angelis"), ("Communion", "Dominus dabit")):
            slot = ServiceRole.objects.create(service=self.service, role_name=name)
            RolePiece.objects.create(service_role=slot, reference=reference, is_confirmed=True)
        RolePiece.objects.create(service_role=self.slot, reference="NEH 1", is_confirmed=True)

    def names(self, groups):
        return [[row["role_name"] for row in group] for group in groups]

    def test_in_service_order_is_one_group(self):
        self.assertEqual(self.names(self.service.music_list_groups()), [
            ["Entrance hymn", "Introit", "Kyrie", "Communion"],
        ])

    def test_propers_beside_the_rest_is_two_groups_each_in_order(self):
        self.assertEqual(self.names(self.service.music_list_groups(arrangement="propers_beside")), [
            ["Introit", "Communion"],
            ["Entrance hymn", "Kyrie"],
        ])

    def test_a_service_with_no_propers_has_one_group_either_way(self):
        self.service.roles.filter(kind="proper").delete()
        self.assertEqual(len(self.service.music_list_groups(arrangement="propers_beside")), 1)

    def test_the_music_list_follows_the_setting(self):
        from core.models import SiteConfig

        config = SiteConfig.of(self.church)
        config.music_list_arrangement = "propers_beside"
        config.save()
        self.client.force_login(self.conductor)
        response = self.client.get(f"/terms/{self.service.term.pk}/music-list/")
        self.assertEqual(response.content.decode().count("<dl>"), 2)
