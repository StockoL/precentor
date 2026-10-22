from datetime import date

from django.test import TestCase
from django.urls import reverse

from accounts.testing import make_organisation, make_user
from ordo.models import LiturgicalOccasion
from precentor_project.testing import make_score, make_slot_template, make_term

from .forms import ServiceForm, TermForm, TermMarkerForm
from .models import RolePiece, Service, ServiceRole, Term, TermMarker


class ServiceStatusTests(TestCase):
    def setUp(self):
        self.term = make_term(
            name="Test Term",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            calendar_use="current",
        )
        self.service = Service.objects.create(
            term=self.term, date=date(2026, 1, 11), service_type="Sung Mass"
        )
        self.score = make_score(title="Test Anthem", composer_surname="Test Composer")

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

    def test_status_needs_no_queries_once_prefetched(self):
        role = ServiceRole.objects.create(service=self.service, role_name="Anthem")
        RolePiece.objects.create(service_role=role, score=self.score, is_confirmed=True)
        service = Service.objects.prefetch_related("roles__pieces").get(pk=self.service.pk)
        with self.assertNumQueries(0):
            self.assertEqual(service.status, "complete")

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
        self.client.force_login(make_user("conductor"))
        for url in (self.service.get_absolute_url(), self.term.get_absolute_url()):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, "badge--not_started")
                self.assertContains(response, ">Not started<")
                self.assertNotContains(response, ">not_started<")


class ServiceEffectiveCalendarUseTests(TestCase):
    def setUp(self):
        self.term = make_term(
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
        self.user = make_user("conductor")
        self.client.force_login(self.user)
        self.term = make_term(
            name="Test Term",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            calendar_use="current",
        )
        self.service = Service.objects.create(
            term=self.term, date=date(2026, 1, 11), service_type="Sung Mass"
        )
        self.score = make_score(title="Test Anthem", composer_surname="Test Composer")

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

    def test_add_piece_non_ajax_invalid_shows_the_page_with_errors(self):
        role = ServiceRole.objects.create(service=self.service, role_name="Anthem")

        response = self.client.post(f"/roles/{role.pk}/pieces/add/", {"score": ""})

        self.assertEqual(role.pieces.count(), 0)
        self.assertTemplateUsed(response, "planning/add_piece.html")
        self.assertContains(response, "errorlist")

    def test_add_piece_page_lists_suggested_scores(self):
        role = ServiceRole.objects.create(service=self.service, role_name="Anthem")

        response = self.client.get(f"/roles/{role.pk}/pieces/add/")

        self.assertContains(response, "<h1>Propose a piece</h1>", html=True)
        self.assertContains(response, "For the Anthem at")
        self.assertContains(response, f'<option value="{self.score.pk}">')

    def test_add_piece_page_is_for_conductors_only(self):
        role = ServiceRole.objects.create(service=self.service, role_name="Anthem")
        self.client.force_login(make_user("librarian"))

        response = self.client.get(f"/roles/{role.pk}/pieces/add/")

        # Refused outright, not sent back to the login page they're past.
        self.assertEqual(response.status_code, 403)

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


class ServiceSuggestedScoresTests(TestCase):
    def setUp(self):
        from ordo.models import LiturgicalSeason

        self.term = make_term(
            name="Test Term",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            calendar_use="current",
        )
        self.advent = LiturgicalSeason.objects.create(name="Advent")
        self.occasion = LiturgicalOccasion.objects.create(
            name="Advent Sunday 4", season=self.advent
        )
        # The untagged score comes first by title, so only the ranking
        # can put the other one ahead of it.
        self.untagged = make_score(title="Aaa Untagged", composer_surname="Nobody")
        self.suited = make_score(title="Zzz Suited", composer_surname="Somebody")

    def make_service(self, occasion=None):
        return Service.objects.create(
            term=self.term, date=date(2026, 1, 11), service_type="Sung Mass",
            occasion=occasion,
        )

    def test_occasion_tag_ranks_first(self):
        self.suited.suited_occasions.add(self.occasion)
        scores = list(self.make_service(self.occasion).suggested_scores())
        self.assertEqual(scores, [self.suited, self.untagged])

    def test_tag_on_the_occasions_season_ranks_first(self):
        self.suited.suited_seasons.add(self.advent)
        scores = list(self.make_service(self.occasion).suggested_scores())
        self.assertEqual(scores, [self.suited, self.untagged])

    def test_without_an_occasion_scores_are_in_title_order(self):
        self.suited.suited_seasons.add(self.advent)
        scores = list(self.make_service().suggested_scores())
        self.assertEqual(scores, [self.untagged, self.suited])


class ServiceDetailProposePieceRankingTests(TestCase):
    def setUp(self):
        self.user = make_user("conductor")
        self.client.force_login(self.user)
        self.term = make_term(
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
        self.untagged = make_score(title="Zzz Untagged", composer_surname="Nobody")
        self.matching = make_score(title="Aaa Matching", composer_surname="Somebody")
        self.matching.suited_occasions.add(self.occasion)

    def test_score_options_ordered_with_suited_score_first(self):
        response = self.client.get(self.service.get_absolute_url())
        values = [option["value"] for option in response.context["score_options"]]
        self.assertEqual(values, [str(self.matching.pk), str(self.untagged.pk)])

    def test_scores_are_sent_once_not_once_per_slot(self):
        ServiceRole.objects.create(service=self.service, role_name="Offertory")

        response = self.client.get(self.service.get_absolute_url())

        self.assertContains(response, 'id="score-options"', count=1)
        self.assertContains(response, "Zzz Untagged", count=1)
        self.assertNotContains(response, "<select")
        # Each slot links to its own propose page for when JavaScript is off.
        for role in self.service.roles.all():
            self.assertContains(response, reverse("planning:add_piece", args=[role.pk]))

    def test_query_count_does_not_grow_with_slots(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        def count():
            url = self.service.get_absolute_url()
            self.client.get(url)
            with CaptureQueriesContext(connection) as captured:
                self.client.get(url)
            return len(captured)

        before = count()
        for name in ("Introit", "Offertory", "Communion"):
            ServiceRole.objects.create(service=self.service, role_name=name)
        self.assertEqual(count(), before)


class TermPageMixin:
    """Set-up shared by the Terms page and term page tests."""

    def setUp(self):
        from datetime import timedelta

        from django.utils import timezone

        self.user = make_user("conductor")
        self.client.force_login(self.user)
        self.today = timezone.localdate()
        self.days = lambda n: self.today + timedelta(days=n)
        self.score = make_score(title="Ave verum", composer_surname="Byrd")

    def make_term(self, name, start, end, services=()):
        """services: (days from today, [(slot name, confirmed)]) pairs."""
        term = make_term(
            name=name, start_date=self.days(start), end_date=self.days(end),
            calendar_use="current",
        )
        made = []
        for offset, slots in services:
            service = Service.objects.create(
                term=term, date=self.days(offset), service_type="Sung Mass"
            )
            for slot, confirmed in slots:
                role = ServiceRole.objects.create(service=service, role_name=slot)
                RolePiece.objects.create(service_role=role, score=self.score, is_confirmed=confirmed)
            made.append(service)
        return term, made

    def count_queries(self, url):
        """Queries for one request to url, after a warm-up request: the
        first request in a test also loads the session and fills
        Django's content-type cache, which later ones don't repeat."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        self.client.get(url)
        with CaptureQueriesContext(connection) as captured:
            self.client.get(url)
        return len(captured)


class TermListPageTests(TermPageMixin, TestCase):

    def test_card_shows_phase_progress_and_next_service(self):
        from comments.models import Comment

        term, services = self.make_term("Michaelmas", -20, 60, services=[
            (-7, [("Setting", True)]),
            (5, [("Setting", True), ("Offertory motet", False)]),
            (30, []),
        ])
        piece = RolePiece.objects.filter(service_role__service=services[1]).first()
        for target in (term, services[0], piece):
            Comment.objects.create(author=self.user, body="Query", target=target)
        Comment.objects.create(author=self.user, body="Done", target=term, is_open=False)

        response = self.client.get("/")
        self.assertContains(response, '<span class="badge badge--current">Current</span>', html=True)
        self.assertContains(response, "Week 3 of 12")
        self.assertContains(response, "1 of 3 services complete, 1 in progress, 1 not started")
        self.assertContains(response, "still to settle: Offertory motet")
        self.assertContains(response, "data-soon")  # five days away, something unsettled
        self.assertContains(response, "3 open comments")  # term, service and piece; not the closed one
        self.assertNotContains(response, "Ready to publish")

    def test_a_fully_planned_term_is_ready_to_publish(self):
        self.make_term("Advent", 10, 40, services=[(14, [("Setting", True)])])
        response = self.client.get("/")
        self.assertContains(response, "Ready to publish")
        self.assertContains(response, "all settled")
        self.assertNotContains(response, "data-soon")

    def test_current_and_upcoming_first_and_past_terms_folded_away(self):
        self.make_term("Lent", 40, 90)
        self.make_term("Michaelmas", -20, 60)
        self.make_term("Easter", -200, -120)
        response = self.client.get("/")
        self.assertEqual([t.name for t in response.context["active_terms"]], ["Michaelmas", "Lent"])
        self.assertEqual([t.name for t in response.context["past_terms"]], ["Easter"])
        self.assertContains(response, "<summary>Past terms (1)</summary>", html=True)

    def test_query_count_does_not_grow_with_more_terms(self):
        services = [(-7, [("Setting", True), ("Motet", False)]), (7, [("Setting", False)])]
        self.make_term("One", -20, 60, services=services)
        one_term = self.count_queries("/")
        self.make_term("Two", 70, 120, services=services)
        self.make_term("Three", -200, -120, services=services)
        self.assertEqual(self.count_queries("/"), one_term)


class TermDetailPageTests(TermPageMixin, TestCase):
    def test_shows_status_and_each_services_details(self):
        occasion = LiturgicalOccasion.objects.create(name="Christ the King", colour="white")
        term, services = self.make_term("Michaelmas", -20, 60, services=[
            (-7, [("Setting", True)]),
            (5, [("Setting", True), ("Offertory motet", False), ("Communion", False)]),
        ])
        services[1].occasion = occasion
        services[1].save()
        response = self.client.get(term.get_absolute_url())
        self.assertContains(response, '<span class="badge badge--current">Current</span>', html=True)
        self.assertContains(response, "1 of 2 services complete, 1 in progress")
        self.assertContains(response, "Christ the King")
        self.assertContains(response, "2 slots to settle")

    def test_query_count_does_not_grow_with_more_services(self):
        term, _ = self.make_term("Michaelmas", -20, 60, services=[(-7, [("Setting", True)])])
        one_service = self.count_queries(term.get_absolute_url())
        for offset in (1, 8, 15):
            service = Service.objects.create(
                term=term, date=self.days(offset), service_type="Vespers"
            )
            role = ServiceRole.objects.create(service=service, role_name="Magnificat")
            RolePiece.objects.create(service_role=role, score=self.score)
        self.assertEqual(self.count_queries(term.get_absolute_url()), one_service)


class TermTimingTests(TestCase):
    def setUp(self):
        # Michaelmas: Sun 6 Sep to Fri 25 Dec 2026, 111 days, so 16 weeks.
        self.term = Term(
            name="Michaelmas 2026",
            start_date=date(2026, 9, 6),
            end_date=date(2026, 12, 25),
            calendar_use="current",
        )

    def test_current_term_counts_weeks_from_its_first_day(self):
        for today, label in [
            (date(2026, 9, 6), "Week 1 of 16"),
            (date(2026, 9, 12), "Week 1 of 16"),
            (date(2026, 9, 13), "Week 2 of 16"),
            (date(2026, 12, 25), "Week 16 of 16"),
        ]:
            with self.subTest(today=today):
                self.assertEqual(self.term.phase(today), "current")
                self.assertEqual(self.term.timing_label(today), label)

    def test_upcoming_term_counts_down(self):
        for today, label in [
            (date(2026, 9, 5), "Starts tomorrow"),
            (date(2026, 8, 30), "Starts in 7 days"),
            (date(2026, 8, 23), "Starts in 2 weeks"),
            (date(2026, 7, 1), "Starts in 9 weeks"),
        ]:
            with self.subTest(today=today):
                self.assertEqual(self.term.phase(today), "upcoming")
                self.assertEqual(self.term.timing_label(today), label)

    def test_past_term_says_when_it_ended(self):
        today = date(2027, 1, 4)
        self.assertEqual(self.term.phase(today), "past")
        self.assertEqual(self.term.phase_label(today), "Past")
        self.assertEqual(self.term.timing_label(today), "Ended Fri 25 Dec 2026")


class RolePieceHistoryStateTests(TestCase):
    def test_sung_scheduled_or_proposed(self):
        from datetime import timedelta

        from django.utils import timezone

        today = timezone.localdate()
        term = make_term(
            name="Term",
            start_date=today - timedelta(days=60),
            end_date=today + timedelta(days=60),
            calendar_use="current",
        )
        score = make_score(title="Ave verum", composer_surname="Byrd")

        def piece(days, confirmed):
            service = Service.objects.create(
                term=term, date=today + timedelta(days=days), service_type="Sung Mass"
            )
            role = ServiceRole.objects.create(service=service, role_name="Motet")
            return RolePiece.objects.create(service_role=role, score=score, is_confirmed=confirmed)

        cases = [
            (piece(-7, True), "sung", "Sung"),
            (piece(0, True), "sung", "Sung"),  # today counts as sung
            (piece(7, True), "scheduled", "Scheduled"),
            (piece(-7, False), "proposed", "Proposed"),
            (piece(7, False), "proposed", "Proposed"),
        ]
        for rolepiece, state, label in cases:
            with self.subTest(state=state, date=rolepiece.service_role.service.date):
                self.assertEqual(rolepiece.history_state, state)
                self.assertEqual(rolepiece.history_label, label)


class ServiceNeighbourLinkTests(TestCase):
    def setUp(self):
        self.client.force_login(make_user("conductor"))
        term = make_term(
            name="Term", start_date=date(2026, 1, 1), end_date=date(2026, 3, 31),
            calendar_use="current",
        )
        other = make_term(
            name="Other", start_date=date(2026, 1, 1), end_date=date(2026, 3, 31),
            calendar_use="current",
        )
        make = lambda t, d, kind: Service.objects.create(term=t, date=d, service_type=kind)
        self.first = make(term, date(2026, 1, 4), "Sung Mass")
        self.middle = make(term, date(2026, 1, 11), "Sung Mass")
        self.last = make(term, date(2026, 1, 11), "Vespers")  # same day, later id
        make(other, date(2026, 1, 7), "Sung Mass")  # another term: never a neighbour

    def test_middle_service_links_both_ways(self):
        response = self.client.get(self.middle.get_absolute_url())
        self.assertContains(response, f'rel="prev" href="{self.first.get_absolute_url()}"')
        self.assertContains(response, f'rel="next" href="{self.last.get_absolute_url()}"')

    def test_ends_link_one_way(self):
        first = self.client.get(self.first.get_absolute_url())
        self.assertNotContains(first, 'rel="prev"')
        self.assertContains(first, f'rel="next" href="{self.middle.get_absolute_url()}"')
        last = self.client.get(self.last.get_absolute_url())
        self.assertContains(last, f'rel="prev" href="{self.middle.get_absolute_url()}"')
        self.assertNotContains(last, 'rel="next"')


class ServiceDetailListTests(TestCase):
    def test_facts_are_a_description_list_including_hymns_and_psalm(self):
        self.client.force_login(make_user("conductor"))
        term = make_term(
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

        self.user = make_user("conductor")
        self.term = make_term(
            name="Test Term",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            calendar_use="current",
        )
        self.service = Service.objects.create(
            term=self.term, date=date(2026, 1, 11), service_type="Sung Mass"
        )
        Service.objects.create(term=self.term, date=date(2026, 1, 18), service_type="Vespers")
        score = make_score(title="Ave verum", composer_surname="Byrd")
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
        self.client.force_login(make_user("conductor"))
        term = make_term(
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
        self.client.force_login(make_user("conductor"))
        self.term = make_term(
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
        self.client.force_login(make_user("conductor"))
        term = make_term(
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
        term = make_term(
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
        self.user = make_user("conductor")
        self.client.force_login(self.user)
        self.term = make_term(
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
        self.user = make_user("viewer")
        self.client.force_login(self.user)
        self.term = make_term(
            name="Test Term",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            calendar_use="current",
        )
        self.service = Service.objects.create(
            term=self.term, date=date(2026, 1, 11), service_type="Sung Mass"
        )
        self.score = make_score(title="Test Anthem", composer_surname="Test Composer")

    def test_page_sends_no_html_comments(self):
        TermMarker.objects.create(term=self.term, date=date(2026, 1, 20), text="Half term")
        response = self.client.get(f"/terms/{self.term.pk}/music-list/")
        self.assertContains(response, "Half term")
        self.assertContains(response, "Sung Mass")
        self.assertNotContains(response, "<!--")

    def test_print_button_has_no_inline_handler(self):
        response = self.client.get(f"/terms/{self.term.pk}/music-list/")
        self.assertNotContains(response, "onclick")
        self.assertContains(
            response,
            '<button type="button" class="btn-primary" data-print hidden>Print</button>',
            html=True,
        )
        self.assertContains(response, "src/js/print-button.js")

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


class ServiceFormOccasionChoicesTests(TestCase):
    """The occasion menus follow the national calendar chosen on Settings."""

    @classmethod
    def setUpTestData(cls):
        from core.models import SiteConfig
        from ordo.calendar_data import load_calendar_files

        load_calendar_files()
        config = SiteConfig.get_solo()
        config.national_calendar = "england"
        config.save()
        cls.term = make_term(
            name="Easter Term", start_date=date(2026, 4, 1), end_date=date(2026, 7, 31), calendar_use="current"
        )

    def labels(self, form, field):
        return [label for _, label in form.fields[field].choices]

    def test_englands_days_in_both_forms_and_not_another_countrys(self):
        labels = self.labels(ServiceForm(), "occasion")
        self.assertIn("Saint George, Martyr, Patron of England", labels)
        self.assertIn("St. George, Martyr, Patron of England (1962)", labels)
        self.assertNotIn("St. David, Bishop & Confessor, Patron of Wales (1962)", labels)
        # Both menus offer the same occasions; the single one starts blank.
        self.assertEqual(labels[1:], self.labels(ServiceForm(), "additional_occasions"))

    def test_a_services_own_occasions_stay_listed(self):
        david = LiturgicalOccasion.objects.get(calendar="wales", key="sancti:03-01wa")
        service = Service.objects.create(term=self.term, date=date(2026, 3, 2), service_type="Mass", occasion=david)
        self.assertIn(david.choice_label, self.labels(ServiceForm(instance=service), "occasion"))

    def test_the_page_tells_the_suggestions_which_calendar(self):
        self.client.force_login(make_user("conductor"))
        response = self.client.get(f"/terms/{self.term.pk}/services/add/")
        self.assertContains(response, 'data-national-calendar="england"')


class MusicListCrestTests(TestCase):
    def setUp(self):
        from core.models import SiteConfig

        self.client.force_login(make_user("viewer"))
        self.term = make_term(
            name="Lent", start_date=date(2026, 1, 1), end_date=date(2026, 3, 31), calendar_use="current"
        )
        self.config = SiteConfig.get_solo()
        self.config.church_name = "St Cecilia's"
        self.config.save()

    def page(self, style=None):
        if style:
            self.config.crest_style = style
            self.config.set_crest(b"image bytes", "image/png")
            self.config.save()
        return self.client.get(f"/terms/{self.term.pk}/music-list/")

    def test_without_a_crest_the_name_is_written(self):
        response = self.page()
        self.assertContains(response, '<p class="music-list-church-name">St Cecilia&#x27;s</p>', html=True)
        self.assertNotContains(response, "/settings/crest/")

    def test_a_logo_sits_beside_the_written_name(self):
        response = self.page("logo")
        self.assertContains(response, f'<img class="music-list-crest" src="{self.config.crest_url}" alt="">', html=True)
        self.assertContains(response, "music-list-church-name")

    def test_a_banner_carries_the_name_so_it_is_not_written_again(self):
        response = self.page("banner")
        self.assertContains(
            response, f'<img class="music-list-banner" src="{self.config.crest_url}" alt="St Cecilia&#x27;s">', html=True
        )
        self.assertNotContains(response, "music-list-church-name")


class PlanningOrganisationTests(TestCase):
    def test_terms_and_templates_belong_to_an_organisation(self):
        church = make_organisation()
        term = make_term(
            name="Lent", start_date=date(2026, 1, 1), end_date=date(2026, 3, 31),
            calendar_use="current", organisation=church,
        )
        template = make_slot_template(name="Benediction", slot_names="O salutaris", organisation=church)
        self.assertEqual(list(church.terms.all()), [term])
        self.assertEqual(list(church.slot_templates.all()), [template])

    def test_services_and_notices_take_their_terms_organisation(self):
        church = make_organisation()
        term = make_term(
            name="Lent", start_date=date(2026, 1, 1), end_date=date(2026, 3, 31),
            calendar_use="current", organisation=church,
        )
        service = Service.objects.create(term=term, date=date(2026, 1, 11), service_type="Sung Mass")
        notice = TermMarker.objects.create(term=term, date=date(2026, 2, 16), text="Half term")
        self.assertEqual((service.organisation, notice.organisation), (church, church))

    def test_slots_and_pieces_take_their_services_organisation(self):
        church = make_organisation()
        term = make_term(
            name="Lent", start_date=date(2026, 1, 1), end_date=date(2026, 3, 31),
            calendar_use="current", organisation=church,
        )
        service = Service.objects.create(term=term, date=date(2026, 1, 11), service_type="Sung Mass")
        slot = ServiceRole.objects.create(service=service, role_name="Offertory motet")
        score = make_score(title="Ave verum", composer_surname="Byrd", organisation=church)
        piece = RolePiece.objects.create(service_role=slot, score=score)
        self.assertEqual((slot.organisation, piece.organisation), (church, church))

    def test_terms_and_templates_made_through_the_app_join_the_makers_organisation(self):
        from .models import SlotTemplate

        church = make_organisation("St Cecilia's")
        self.client.force_login(make_user("conductor", organisation=church))
        self.client.post("/terms/add/", {
            "name": "Advent", "start_date": "2026-11-29", "end_date": "2026-12-24", "calendar_use": "current",
        })
        self.client.post("/templates/add/", {"name": "Compline", "slot_names": "Nunc dimittis"})
        self.assertEqual(Term.objects.get(name="Advent").organisation, church)
        self.assertEqual(SlotTemplate.objects.get(name="Compline").organisation, church)
