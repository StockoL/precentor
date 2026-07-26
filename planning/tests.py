from datetime import date

from django.test import TestCase

from library.models import Score

from .models import RolePiece, Service, ServiceRole, Term


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
        self.term = Term.objects.create(
            name="Test Term", start_date=date(2026, 1, 1), end_date=date(2026, 3, 31)
        )
        self.service = Service.objects.create(
            term=self.term, date=date(2026, 1, 11), service_type="Sung Eucharist"
        )
        self.score = Score.objects.create(title="Test Anthem", composer="Test Composer")

    def test_add_role(self):
        self.client.post(
            f"/planning/services/{self.service.pk}/roles/add/", {"role_name": "Anthem"}
        )
        self.assertEqual(self.service.roles.count(), 1)

    def test_add_piece_and_toggle_confirm(self):
        role = ServiceRole.objects.create(service=self.service, role_name="Anthem")
        self.client.post(
            f"/planning/roles/{role.pk}/pieces/add/", {"score": self.score.pk}
        )
        piece = role.pieces.first()
        self.assertFalse(piece.is_confirmed)

        self.client.post(f"/planning/pieces/{piece.pk}/toggle-confirm/")
        piece.refresh_from_db()
        self.assertTrue(piece.is_confirmed)

    def test_get_request_rejected(self):
        response = self.client.get(f"/planning/services/{self.service.pk}/roles/add/")
        self.assertEqual(response.status_code, 405)
