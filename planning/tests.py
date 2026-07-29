from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase

from library.models import Score
from ordo.models import LiturgicalOccasion

from .models import RolePiece, Service, ServiceRole, Term

User = get_user_model()


class ServiceStatusTests(TestCase):
    def setUp(self):
        self.term = Term.objects.create(
            name="Test Term",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            tradition="cofe",
            calendar_use="current",
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


class ServiceEffectiveTraditionTests(TestCase):
    def setUp(self):
        self.term = Term.objects.create(
            name="Test Term",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            tradition="cofe",
            calendar_use="current",
        )

    def test_falls_back_to_term_when_unset(self):
        service = Service.objects.create(
            term=self.term, date=date(2026, 1, 11), service_type="Sung Eucharist"
        )
        self.assertEqual(service.effective_tradition(), "cofe")
        self.assertEqual(service.effective_calendar_use(), "current")

    def test_uses_own_value_when_set(self):
        service = Service.objects.create(
            term=self.term,
            date=date(2026, 1, 11),
            service_type="Sung Eucharist",
            tradition="catholic",
            calendar_use="historic",
        )
        self.assertEqual(service.effective_tradition(), "catholic")
        self.assertEqual(service.effective_calendar_use(), "historic")


class RolePieceWorkflowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="conductor", password="testpass123"
        )
        self.user.groups.add(Group.objects.get_or_create(name="Conductor")[0])
        self.client.login(username="conductor", password="testpass123")
        self.term = Term.objects.create(
            name="Test Term",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            tradition="cofe",
            calendar_use="current",
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

    def test_toggle_confirm_ajax_returns_fragments(self):
        role = ServiceRole.objects.create(service=self.service, role_name="Anthem")
        piece = RolePiece.objects.create(service_role=role, score=self.score)

        response = self.client.post(
            f"/pieces/{piece.pk}/toggle-confirm/",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        fragments = response.json()["fragments"]
        self.assertIn(f"piece-row-{piece.pk}", fragments)
        self.assertIn("service-status-badge", fragments)
        self.assertIn("Un-confirm", fragments[f"piece-row-{piece.pk}"])

    def test_add_piece_ajax_success_returns_new_piece_fragment(self):
        role = ServiceRole.objects.create(service=self.service, role_name="Anthem")

        response = self.client.post(
            f"/roles/{role.pk}/pieces/add/",
            {"score": self.score.pk},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        piece = role.pieces.get()
        fragments = response.json()["fragments"]
        self.assertEqual(list(fragments.keys()), [f"piece-row-{piece.pk}"])
        self.assertIn("Test Anthem", fragments[f"piece-row-{piece.pk}"])

    def test_add_piece_ajax_invalid_returns_400_with_form_fragment(self):
        role = ServiceRole.objects.create(service=self.service, role_name="Anthem")

        response = self.client.post(
            f"/roles/{role.pk}/pieces/add/",
            {"score": ""},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(role.pieces.count(), 0)
        fragments = response.json()["fragments"]
        self.assertIn(f"add-piece-form-{role.pk}", fragments)
        self.assertIn("errorlist", fragments[f"add-piece-form-{role.pk}"])

    def test_add_piece_non_ajax_invalid_sets_error_message(self):
        role = ServiceRole.objects.create(service=self.service, role_name="Anthem")

        response = self.client.post(
            f"/roles/{role.pk}/pieces/add/", {"score": ""}, follow=True
        )

        self.assertEqual(role.pieces.count(), 0)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertIn("Couldn't add that piece", str(messages[0]))

    def test_add_role_ajax_success_returns_role_block_and_status_badge(self):
        response = self.client.post(
            f"/services/{self.service.pk}/roles/add/",
            {"role_name": "Anthem"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        role = self.service.roles.get()
        fragments = response.json()["fragments"]
        self.assertEqual(
            set(fragments.keys()), {f"role-block-{role.pk}", "service-status-badge"}
        )
        self.assertIn("Anthem", fragments[f"role-block-{role.pk}"])
        # A brand-new role has no pieces yet, so status stays not_started
        # (matches Service.status: resolved_count == 0 and not has_any_piece).
        self.assertIn("not_started", fragments["service-status-badge"])

    def test_add_role_ajax_invalid_returns_400_with_form_fragment(self):
        response = self.client.post(
            f"/services/{self.service.pk}/roles/add/",
            {"role_name": ""},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.service.roles.count(), 0)
        fragments = response.json()["fragments"]
        self.assertIn("add-role-form", fragments)
        self.assertIn("errorlist", fragments["add-role-form"])

    def test_add_role_non_ajax_invalid_sets_error_message(self):
        response = self.client.post(
            f"/services/{self.service.pk}/roles/add/", {"role_name": ""}, follow=True
        )

        self.assertEqual(self.service.roles.count(), 0)
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertIn("Couldn't add that role", str(messages[0]))


class ServiceDetailProposePieceRankingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="conductor", password="testpass123"
        )
        self.client.login(username="conductor", password="testpass123")
        self.term = Term.objects.create(
            name="Test Term",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            tradition="cofe",
            calendar_use="current",
        )
        self.occasion = LiturgicalOccasion.objects.create(
            name="Advent Sunday 4", tradition="cofe"
        )
        self.service = Service.objects.create(
            term=self.term,
            date=date(2026, 1, 11),
            service_type="Sung Eucharist",
            occasion=self.occasion,
        )
        ServiceRole.objects.create(service=self.service, role_name="Anthem")
        self.untagged = Score.objects.create(title="Zzz Untagged", composer="Nobody")
        self.matching = Score.objects.create(title="Aaa Matching", composer="Somebody")
        self.matching.suited_occasions.add(self.occasion)

    def test_score_options_ordered_with_suited_score_first(self):
        response = self.client.get(self.service.get_absolute_url())
        role = self.service.roles.get()
        queryset = list(response.context["roles"][0].piece_form.fields["score"].queryset)
        self.assertEqual(queryset[0], self.matching)
        self.assertIn(self.untagged, queryset)


class TermDetailViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="conductor", password="testpass123"
        )
        self.client.login(username="conductor", password="testpass123")
        self.term = Term.objects.create(
            name="Test Term",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            tradition="cofe",
            calendar_use="current",
        )

    def test_service_list_links_to_service_detail(self):
        service = Service.objects.create(
            term=self.term, date=date(2026, 1, 11), service_type="Sung Eucharist"
        )
        response = self.client.get(self.term.get_absolute_url())
        self.assertContains(response, service.get_absolute_url())


class MusicListTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="conductor", password="testpass123"
        )
        self.client.login(username="conductor", password="testpass123")
        self.term = Term.objects.create(
            name="Test Term",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            tradition="cofe",
            calendar_use="current",
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
