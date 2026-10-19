from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from library.models import Score
from ordo.models import LiturgicalOccasion

from .forms import ServiceForm, TermForm, TermMarkerForm
from .models import RolePiece, Service, ServiceRole, Term, TermMarker

User = get_user_model()


class ServiceStatusTests(TestCase):
    def setUp(self):
        self.term = Term.objects.create(
            name="Test Term",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            calendar_use="current",
        )
        self.service = Service.objects.create(
            term=self.term, date=date(2026, 1, 11), service_type="Sung Mass"
        )
        self.score = Score.objects.create(title="Test Anthem", composer_surname="Test Composer")

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

    def test_str_uses_the_ui_date_format(self):
        # __str__ feeds the service page's heading and tab title.
        self.assertEqual(str(self.service), "Sung Mass — Sun 11 Jan 2026")
        marker = TermMarker(term=self.term, date=date(2026, 2, 16), text="Half term")
        self.assertEqual(str(marker), "Half term (Mon 16 Feb 2026)")

    def test_status_label_is_readable(self):
        self.assertEqual(self.service.status_label, "Not started")
        role = ServiceRole.objects.create(service=self.service, role_name="Anthem")
        piece = RolePiece.objects.create(service_role=role, score=self.score)
        self.assertEqual(self.service.status_label, "In progress")
        piece.is_confirmed = True
        piece.save()
        self.assertEqual(self.service.status_label, "Complete")

    def test_badges_show_label_and_keep_raw_value_as_class(self):
        user = User.objects.create_superuser(username="admin", password="testpass123")
        self.client.force_login(user)
        for url in (self.service.get_absolute_url(), self.term.get_absolute_url()):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, "badge--not_started")
                self.assertContains(response, ">Not started<")
                self.assertNotContains(response, ">not_started<")


class ServiceEffectiveCalendarUseTests(TestCase):
    def setUp(self):
        self.term = Term.objects.create(
            name="Test Term",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            calendar_use="current",
        )

    def test_falls_back_to_term_when_unset(self):
        service = Service.objects.create(
            term=self.term, date=date(2026, 1, 11), service_type="Sung Mass"
        )
        self.assertEqual(service.effective_calendar_use(), "current")

    def test_uses_own_value_when_set(self):
        service = Service.objects.create(
            term=self.term,
            date=date(2026, 1, 11),
            service_type="Sung Mass",
            calendar_use="historic",
        )
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
            calendar_use="current",
        )
        self.service = Service.objects.create(
            term=self.term, date=date(2026, 1, 11), service_type="Sung Mass"
        )
        self.score = Score.objects.create(title="Test Anthem", composer_surname="Test Composer")

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
        self.assertIn("Unconfirm", fragments[f"piece-row-{piece.pk}"])

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
        self.assertIn("Couldn't add that slot", str(messages[0]))


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
            calendar_use="current",
        )
        self.occasion = LiturgicalOccasion.objects.create(
            name="Advent Sunday 4"
        )
        self.service = Service.objects.create(
            term=self.term,
            date=date(2026, 1, 11),
            service_type="Sung Mass",
            occasion=self.occasion,
        )
        ServiceRole.objects.create(service=self.service, role_name="Anthem")
        self.untagged = Score.objects.create(title="Zzz Untagged", composer_surname="Nobody")
        self.matching = Score.objects.create(title="Aaa Matching", composer_surname="Somebody")
        self.matching.suited_occasions.add(self.occasion)

    def test_score_options_ordered_with_suited_score_first(self):
        response = self.client.get(self.service.get_absolute_url())
        role = self.service.roles.get()
        queryset = list(response.context["roles"][0].piece_form.fields["score"].queryset)
        self.assertEqual(queryset[0], self.matching)
        self.assertIn(self.untagged, queryset)


class ServiceDetailListTests(TestCase):
    def test_facts_are_a_description_list_including_hymns_and_psalm(self):
        self.client.force_login(
            User.objects.create_superuser(username="admin", password="testpass123")
        )
        term = Term.objects.create(
            name="Test Term",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            calendar_use="current",
        )
        service = Service.objects.create(
            term=term, date=date(2026, 1, 11), service_type="Sung Mass",
            hymns="123, 345", psalm="150",
        )
        response = self.client.get(service.get_absolute_url())
        self.assertContains(response, '<dl class="detail-list">')
        for label, value in (("Hymns", "123, 345"), ("Psalm", "150")):
            with self.subTest(label=label):
                self.assertContains(response, f"<dt>{label}</dt>", html=True)
                self.assertContains(response, f"<dd>{value}</dd>", html=True)
        self.assertNotContains(response, "<p>Term:")


class DeletionSummaryTests(TestCase):
    def setUp(self):
        from comments.models import Comment

        self.user = User.objects.create_superuser(username="admin", password="testpass123")
        self.term = Term.objects.create(
            name="Test Term",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            calendar_use="current",
        )
        self.service = Service.objects.create(
            term=self.term, date=date(2026, 1, 11), service_type="Sung Mass"
        )
        Service.objects.create(term=self.term, date=date(2026, 1, 18), service_type="Vespers")
        score = Score.objects.create(title="Ave verum", composer_surname="Byrd")
        setting = ServiceRole.objects.create(service=self.service, role_name="Setting")
        ServiceRole.objects.create(service=self.service, role_name="Offertory motet")
        piece = RolePiece.objects.create(service_role=setting, score=score)
        RolePiece.objects.create(service_role=setting, score=score)
        TermMarker.objects.create(term=self.term, date=date(2026, 2, 16), text="Half term")
        # One comment at each level: term, service and piece.
        for target in (self.term, self.service, piece):
            Comment.objects.create(author=self.user, body="Query", target=target)

    def test_term_summary_counts_everything_it_takes_with_it(self):
        self.assertEqual(
            self.term.deletion_summary(),
            [(2, "service"), (2, "slot"), (2, "proposed piece"), (1, "notice"), (3, "comment")],
        )

    def test_service_summary_leaves_out_what_it_has_none_of(self):
        self.assertEqual(
            self.service.deletion_summary(),
            [(2, "slot"), (2, "proposed piece"), (2, "comment")],
        )
        empty = Service.objects.get(service_type="Vespers")
        self.assertEqual(empty.deletion_summary(), [])

    def test_delete_page_lists_the_counts(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("planning:term_delete", args=[self.term.pk]))
        for line in ("2 services", "2 slots", "2 proposed pieces", "1 notice", "3 comments"):
            with self.subTest(line=line):
                self.assertContains(response, f"<li>{line}</li>", html=True)
        self.assertContains(response, "This can't be undone.")


class SlotWordingTests(TestCase):
    """A ServiceRole is called a slot in the UI; the model keeps its name."""

    def test_service_page_says_slot_not_role(self):
        self.client.force_login(
            User.objects.create_superuser(username="admin", password="testpass123")
        )
        term = Term.objects.create(
            name="Test Term",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            calendar_use="current",
        )
        service = Service.objects.create(
            term=term, date=date(2026, 1, 11), service_type="Sung Mass"
        )
        response = self.client.get(service.get_absolute_url())
        for text in ("<h2>Slots</h2>", "<h2>Add a slot</h2>", ">Add slot</button>",
                     ">Slot:</label>", ">Not needed (N/A):</label>"):
            with self.subTest(text=text):
                self.assertContains(response, text)
        for text in ("<h2>Roles</h2>", "Add a role", ">Add role<", "Role name"):
            with self.subTest(text=text):
                self.assertNotContains(response, text)


class NoticeWordingTests(TestCase):
    """A TermMarker is called a notice in the UI; the model keeps its name."""

    def setUp(self):
        self.client.force_login(
            User.objects.create_superuser(username="admin", password="testpass123")
        )
        self.term = Term.objects.create(
            name="Test Term",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            calendar_use="current",
        )
        self.marker = TermMarker.objects.create(
            term=self.term, date=date(2026, 2, 16), text="Half term"
        )

    def test_pages_say_notice_not_marker(self):
        pages = {
            self.term.get_absolute_url(): ["<h2>Notices</h2>", ">New notice</a>"],
            reverse("planning:marker_create", args=[self.term.pk]): [
                "<title>New notice — Precentor</title>",
                "<h1>New notice</h1>",
                ">Notice:</label>",
            ],
            reverse("planning:marker_update", args=[self.marker.pk]): [
                "<title>Edit notice — Precentor</title>",
                "<h1>Edit notice</h1>",
            ],
            reverse("planning:marker_delete", args=[self.marker.pk]): [
                "<title>Delete notice — Precentor</title>",
            ],
        }
        for url, texts in pages.items():
            response = self.client.get(url)
            for text in texts:
                with self.subTest(url=url, text=text):
                    self.assertContains(response, text)
            # Visible text only: URLs such as /markers/1/edit/ are fine.
            for old in ("Marker", " marker"):
                with self.subTest(url=url, old=old):
                    self.assertNotContains(response, old)


class PlanningFormLabelTests(TestCase):
    def test_term_and_service_forms_explain_the_calendar(self):
        term_form = str(TermForm())
        self.assertIn("Calendar:</label>", term_form)
        self.assertIn("A service can override it.", term_form)
        service_form = str(ServiceForm())
        self.assertIn("Calendar:</label>", service_form)
        # help_text is not HTML-escaped by Django, so the apostrophe is literal.
        self.assertIn("Leave blank to follow the term's calendar.", service_form)
        self.assertIn("Other occasions:</label>", service_form)
        self.assertNotIn("Calendar use", term_form + service_form)


class ServiceFormLayoutTests(TestCase):
    def test_fields_are_grouped_in_fieldsets(self):
        self.client.force_login(
            User.objects.create_superuser(username="admin", password="testpass123")
        )
        term = Term.objects.create(
            name="Test Term",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            calendar_use="current",
        )
        response = self.client.get(reverse("planning:service_create", args=[term.pk]))
        for legend in ("When", "Liturgy", "Music list"):
            with self.subTest(legend=legend):
                self.assertContains(response, f"<legend>{legend}</legend>", html=True)
        for field in ServiceForm.Meta.fields:
            with self.subTest(field=field):
                self.assertContains(response, f'name="{field}"')


class DateInputValueTests(TestCase):
    """<input type="date"> only accepts an ISO value (YYYY-MM-DD).
    Django otherwise renders a date in the locale's first input format,
    which for en-gb is DD/MM/YYYY, and the browser shows a blank field."""

    def test_edit_forms_render_dates_as_iso(self):
        term = Term.objects.create(
            name="Test Term",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            calendar_use="current",
        )
        service = Service(term=term, date=date(2026, 1, 11))
        marker = TermMarker(term=term, date=date(2026, 2, 16), text="Half term")
        cases = [
            (TermForm(instance=term), "start_date", "2026-01-01"),
            (TermForm(instance=term), "end_date", "2026-03-31"),
            (ServiceForm(instance=service), "date", "2026-01-11"),
            (TermMarkerForm(instance=marker), "date", "2026-02-16"),
        ]
        for form, field, expected in cases:
            with self.subTest(form=type(form).__name__, field=field):
                self.assertIn(f'value="{expected}"', str(form[field]))


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
            calendar_use="current",
        )

    def test_dates_use_the_short_ui_format(self):
        Service.objects.create(
            term=self.term, date=date(2026, 1, 11), service_type="Sung Mass"
        )
        for url in ("/", self.term.get_absolute_url()):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, "Thu 1 Jan 2026 to Tue 31 Mar 2026")
                self.assertNotContains(response, "01/01/2026")
        self.assertContains(
            self.client.get(self.term.get_absolute_url()), "Sun 11 Jan 2026 — Sung Mass"
        )

    def test_empty_term_explains_services_and_notices(self):
        response = self.client.get(self.term.get_absolute_url())
        self.assertContains(response, "No services yet.")
        self.assertContains(response, ">Add the first service</a>")
        self.assertContains(response, "No notices.")
        self.assertContains(response, ">Add a notice</a>")

    def test_service_list_links_to_service_detail(self):
        service = Service.objects.create(
            term=self.term, date=date(2026, 1, 11), service_type="Sung Mass"
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
            calendar_use="current",
        )
        self.service = Service.objects.create(
            term=self.term, date=date(2026, 1, 11), service_type="Sung Mass"
        )
        self.score = Score.objects.create(title="Test Anthem", composer_surname="Test Composer")

    def test_version_toggle_marks_the_version_being_viewed(self):
        url = f"/terms/{self.term.pk}/music-list/"
        public = self.client.get(url)
        self.assertContains(public, '<a href="?" aria-current="page">Public</a>', html=True)
        self.assertContains(public, '<a href="?draft=1">Draft</a>', html=True)
        draft = self.client.get(url + "?draft=1")
        self.assertContains(draft, '<a href="?">Public</a>', html=True)
        self.assertContains(draft, '<a href="?draft=1" aria-current="page">Draft</a>', html=True)

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
