from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase

from library.models import Score

from .models import RolePiece, Service, ServiceRole, Term

User = get_user_model()


class ServiceStatusTests(TestCase):
    def setUp(self):
        self.term = Term.objects.create(
            name="Test Term", start_date=date(2026, 1, 1), end_date=date(2026, 3, 31)
        )
        self.service = Service.objects.create(
            term=self.term, date=date(2026, 1, 11), service_type="Sung Eucharist"
        )
        self.score = Score.objects.create(title="Test Anthem", composer="Test Composer")

    def test_no_roles_is_not_started(self):
        self.assertEqual(self.service.status, "not_started")

    def test_unconfirmed_role_is_in_progress(self):
        role = ServiceRole.objects.create(service=self.service, role_name="Anthem")
        RolePiece.objects.create(
            service_role=role, score=self.score, is_confirmed=False
        )
        self.assertEqual(self.service.status, "in_progress")

    def test_confirmed_role_is_complete(self):
        role = ServiceRole.objects.create(service=self.service, role_name="Anthem")
        RolePiece.objects.create(service_role=role, score=self.score, is_confirmed=True)
        self.assertEqual(self.service.status, "complete")

    def test_na_role_counts_as_resolved(self):
        ServiceRole.objects.create(
            service=self.service, role_name="Setting", is_not_applicable=True
        )
        self.assertEqual(self.service.status, "complete")

    def test_mixed_roles_is_in_progress(self):
        ServiceRole.objects.create(
            service=self.service, role_name="Setting", is_not_applicable=True
        )
        role = ServiceRole.objects.create(service=self.service, role_name="Anthem")
        RolePiece.objects.create(
            service_role=role, score=self.score, is_confirmed=False
        )
        self.assertEqual(self.service.status, "in_progress")


class RolePieceWorkflowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="conductor", password="testpass123"
        )
        self.user.groups.add(Group.objects.get_or_create(name="Conductor")[0])
        self.client.login(username="conductor", password="testpass123")
        self.term = Term.objects.create(
            name="Test Term", start_date=date(2026, 1, 1), end_date=date(2026, 3, 31)
        )
        self.service = Service.objects.create(
            term=self.term, date=date(2026, 1, 11), service_type="Sung Eucharist"
        )
        self.score = Score.objects.create(title="Test Anthem", composer="Test Composer")

    def test_add_role(self):
        self.client.post(
            f"/services/{self.service.pk}/roles/add/", {"role_name": "Anthem"}
        )
        self.assertEqual(self.service.roles.count(), 1)

    def test_add_piece_and_toggle_confirm(self):
        role = ServiceRole.objects.create(service=self.service, role_name="Anthem")
        self.client.post(
            f"/roles/{role.pk}/pieces/add/", {"score": self.score.pk}
        )
        piece = role.pieces.first()
        self.assertFalse(piece.is_confirmed)

        self.client.post(f"/pieces/{piece.pk}/toggle-confirm/")
        piece.refresh_from_db()
        self.assertTrue(piece.is_confirmed)

    def test_get_request_rejected(self):
        response = self.client.get(f"/services/{self.service.pk}/roles/add/")
        self.assertEqual(response.status_code, 405)


class MusicListTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="conductor", password="testpass123"
        )
        self.client.login(username="conductor", password="testpass123")
        self.term = Term.objects.create(
            name="Test Term", start_date=date(2026, 1, 1), end_date=date(2026, 3, 31)
        )
        self.service = Service.objects.create(
            term=self.term, date=date(2026, 1, 11), service_type="Sung Eucharist"
        )
        self.score = Score.objects.create(title="Test Anthem", composer="Test Composer")

    def test_na_role_never_shown(self):
        ServiceRole.objects.create(
            service=self.service, role_name="Setting", is_not_applicable=True
        )
        response = self.client.get(f"/terms/{self.term.pk}/music-list/")
        self.assertNotContains(response, "Setting")

    def test_unconfirmed_role_hidden_in_public_version(self):
        role = ServiceRole.objects.create(service=self.service, role_name="Anthem")
        RolePiece.objects.create(
            service_role=role, score=self.score, is_confirmed=False
        )
        response = self.client.get(f"/terms/{self.term.pk}/music-list/")
        self.assertNotContains(response, "Anthem")

    def test_unconfirmed_role_shown_as_tbc_in_draft(self):
        role = ServiceRole.objects.create(service=self.service, role_name="Anthem")
        RolePiece.objects.create(
            service_role=role, score=self.score, is_confirmed=False
        )
        response = self.client.get(
            f"/terms/{self.term.pk}/music-list/?draft=1"
        )
        self.assertContains(response, "Anthem")
        self.assertContains(response, "TBC")

    def test_confirmed_piece_shown_in_public_version(self):
        role = ServiceRole.objects.create(service=self.service, role_name="Anthem")
        RolePiece.objects.create(service_role=role, score=self.score, is_confirmed=True)
        response = self.client.get(f"/terms/{self.term.pk}/music-list/")
        self.assertContains(response, "Anthem")
        self.assertContains(response, "Test Anthem")
