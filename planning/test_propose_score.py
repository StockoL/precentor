import re
from datetime import timedelta

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from accounts.testing import make_organisation, make_user
from ordo.models import UseType
from precentor_project.test_browser import PlaywrightTestCase
from precentor_project.testing import make_score, make_term

from .models import RolePiece, Service, ServiceRole


class ProposeFromLibraryTestCase(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.church = make_organisation()
        self.conductor = make_user("conductor", organisation=self.church)
        self.client.force_login(self.conductor)
        self.term = make_term(organisation=self.church, name="Michaelmas",
                              start_date=self.today - timedelta(days=30), end_date=self.today + timedelta(days=60))
        self.score = make_score(organisation=self.church, title="Ave verum corpus", composer_surname="Mozart")
        self.url = f"/scores/{self.score.pk}/propose/"

    def service(self, days, service_type="Sung Mass"):
        return Service.objects.create(term=self.term, date=self.today + timedelta(days=days), service_type=service_type)


class ChooseAServiceTests(ProposeFromLibraryTestCase):
    def test_the_score_page_offers_propose_to_those_who_plan(self):
        page = self.client.get(self.score.get_absolute_url())
        self.assertContains(page, f'<a class="btn" href="{self.url}">Propose</a>', html=True)
        for role in ("viewer", "librarian"):
            with self.subTest(role=role):
                self.client.force_login(make_user(role, organisation=self.church))
                self.assertNotContains(self.client.get(self.score.get_absolute_url()), self.url)

    def test_a_viewer_is_refused(self):
        self.client.force_login(make_user("viewer", organisation=self.church))
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_another_churchs_score_is_not_found(self):
        theirs = make_score(organisation=make_organisation("St Elsewhere"), title="Theirs")
        self.assertEqual(self.client.get(f"/scores/{theirs.pk}/propose/").status_code, 404)

    def test_services_from_today_on_soonest_first_with_term_and_status(self):
        self.service(-7, "Past Mass")
        later = self.service(14, "Evensong")
        today = self.service(0)
        options = self.client.get(self.url).context["services"]
        self.assertEqual(options, [today, later])
        page = self.client.get(self.url)
        day = f"{today.date:%a} {today.date.day} {today.date:%b %Y}"
        self.assertContains(page, f"{day}, Sung Mass: Michaelmas (Not started)")
        self.assertNotContains(page, "Past Mass")

    def test_a_service_that_already_has_the_score_is_disabled(self):
        service = self.service(7)
        slot = ServiceRole.objects.create(service=service, role_name="Communion")
        RolePiece.objects.create(service_role=slot, score=self.score)
        page = self.client.get(self.url).content.decode()
        self.assertRegex(page, rf'<option value="{service.pk}" disabled>[^<]*, already proposed</option>')

    def test_the_list_costs_no_query_per_service(self):
        first = ServiceRole.objects.create(service=self.service(1), role_name="Communion")
        RolePiece.objects.create(service_role=first, reference="Something")
        self.client.get(self.url)
        with CaptureQueriesContext(connection) as before:
            self.client.get(self.url)
        for days in range(2, 8):
            service = self.service(days)
            slot = ServiceRole.objects.create(service=service, role_name="Communion")
            RolePiece.objects.create(service_role=slot, reference="Something", is_confirmed=True)
        with self.assertNumQueries(len(before)):
            self.client.get(self.url)


class WithAMassTestCase(ProposeFromLibraryTestCase):
    """A Sung Mass a week away with an Introit holding a reference, and an
    empty Offertory and Communion."""

    def setUp(self):
        super().setUp()
        self.mass = self.service(7)
        self.introit = ServiceRole.objects.create(service=self.mass, role_name="Introit")
        RolePiece.objects.create(service_role=self.introit, reference="Ad te levavi")
        self.offertory = ServiceRole.objects.create(service=self.mass, role_name="Offertory")
        self.communion = ServiceRole.objects.create(service=self.mass, role_name="Communion")


class ChooseASlotTests(WithAMassTestCase):
    def step_two(self, service_pk=None):
        return self.client.get(self.url, {"service": service_pk or self.mass.pk})

    def mark_for(self, *names):
        for name in names:
            use, _ = UseType.objects.get_or_create(organisation=self.church, name=name)
            self.score.suited_use_types.add(use)

    def test_another_churchs_service_or_a_bad_id_is_not_found(self):
        theirs = make_term(organisation=make_organisation("St Elsewhere"), start_date=self.today,
                           end_date=self.today + timedelta(days=30))
        their_service = Service.objects.create(term=theirs, date=self.today, service_type="Sung Mass")
        for value in (their_service.pk, 999999, "abc"):
            with self.subTest(service=value):
                self.assertEqual(self.client.get(self.url, {"service": value}).status_code, 404)

    def test_empty_slots_come_first_each_saying_what_it_holds(self):
        page = self.step_two().content.decode()
        select = page.split('id="propose-slot-select"')[1]
        options = re.findall(r'<option value="(\d+|new)"[^>]*>([^<]*)</option>', select)
        self.assertEqual([label for _, label in options],
                         ["Offertory: empty", "Communion: empty", "Introit: Ad te levavi", "New slot…"])
        self.assertContains(self.step_two(), f'<option value="{self.mass.pk}" selected>', html=False)

    def test_a_clean_match_is_chosen_and_says_why(self):
        self.mark_for("Communion")
        response = self.step_two()
        self.assertEqual(response.context["chosen"], self.communion)
        self.assertContains(response, "Chosen because this score is marked for Communion.")

    def test_otherwise_the_first_empty_slot(self):
        response = self.step_two()
        self.assertEqual(response.context["chosen"], self.offertory)
        self.assertContains(response, "The first empty slot.")
        self.mark_for("Communion", "Offertory")
        response = self.step_two()
        self.assertEqual(response.context["chosen"], self.offertory)
        self.assertContains(response, "The first empty slot, as the score is marked for more than one of these slots.")

    def test_with_no_empty_slot_and_no_match_a_new_slot_is_offered(self):
        for slot in (self.offertory, self.communion):
            RolePiece.objects.create(service_role=slot, reference="Something")
        response = self.step_two()
        self.assertIsNone(response.context["chosen"])
        self.assertContains(response, '<option value="new" selected>New slot…</option>', html=True)
        self.assertContains(response, 'name="new-kind"')
        self.assertNotContains(response, 'name="new-role_name" required')


class ProposeTests(WithAMassTestCase):
    def post(self, **data):
        return self.client.post(self.url, {"service": self.mass.pk, **data})

    def test_proposing_adds_to_the_slot_and_goes_back_to_the_service(self):
        response = self.post(slot=self.communion.pk)
        piece = RolePiece.objects.get(service_role=self.communion)
        self.assertRedirects(response, piece.get_absolute_url(), fetch_redirect_response=False)
        self.assertEqual((piece.score, piece.is_confirmed), (self.score, False))
        page = self.client.get(self.mass.get_absolute_url())
        self.assertContains(page, "Proposed Ave verum corpus (Mozart) for the Communion.")

    def test_propose_and_confirm(self):
        self.post(slot=self.offertory.pk, confirm="1")
        self.assertTrue(RolePiece.objects.get(service_role=self.offertory, score=self.score).is_confirmed)

    def test_it_only_adds(self):
        self.post(slot=self.introit.pk)
        titles = sorted(piece.title for piece in self.introit.pieces.all())
        self.assertEqual(titles, ["Ad te levavi", "Ave verum corpus (Mozart)"])

    def test_the_same_score_twice_in_a_slot_is_refused(self):
        RolePiece.objects.create(service_role=self.communion, score=self.score)
        response = self.post(slot=self.communion.pk)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "That&#x27;s already proposed for this slot.")
        self.assertEqual(RolePiece.objects.filter(score=self.score).count(), 1)
        self.assertEqual(response.context["chosen"], self.communion)

    def test_a_new_slot_is_made_with_the_kind_chosen(self):
        self.post(slot="new", **{"new-role_name": "After Communion", "new-kind": "motet"})
        slot = ServiceRole.objects.get(service=self.mass, role_name="After Communion")
        self.assertEqual(slot.kind, "motet")
        self.assertEqual(slot.pieces.get().score, self.score)

    def test_a_new_slot_needs_a_name_and_nothing_is_saved_without_one(self):
        response = self.post(slot="new", **{"new-role_name": "", "new-kind": "motet"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required.")
        self.assertEqual(self.mass.roles.count(), 3)
        self.assertFalse(RolePiece.objects.filter(score=self.score).exists())

    def test_another_churchs_slot_or_another_services_slot_is_not_found(self):
        theirs = make_term(organisation=make_organisation("St Elsewhere"), start_date=self.today,
                           end_date=self.today + timedelta(days=30))
        their_service = Service.objects.create(term=theirs, date=self.today, service_type="Sung Mass")
        their_slot = ServiceRole.objects.create(service=their_service, role_name="Communion")
        other_slot = ServiceRole.objects.create(service=self.service(9), role_name="Communion")
        for slot in (their_slot.pk, other_slot.pk, "abc"):
            with self.subTest(slot=slot):
                self.assertEqual(self.post(slot=slot).status_code, 404)
        response = self.client.post(self.url, {"service": their_service.pk, "slot": their_slot.pk})
        self.assertEqual(response.status_code, 404)
        self.assertFalse(RolePiece.objects.filter(score=self.score).exists())

    def test_a_viewer_cant_propose(self):
        self.client.force_login(make_user("viewer", organisation=self.church))
        self.assertEqual(self.post(slot=self.communion.pk).status_code, 403)
        self.assertFalse(RolePiece.objects.filter(score=self.score).exists())

    def test_without_javascript_page_by_page(self):
        first = self.client.get(self.url)
        self.assertContains(first, "Show its slots")
        second = self.client.get(self.url, {"service": self.mass.pk})
        self.assertContains(second, 'id="propose-slot-select"')
        self.assertContains(second, ">Propose and confirm</button>")
        response = self.post(slot=second.context["chosen"].pk)
        piece = RolePiece.objects.get(score=self.score)
        self.assertRedirects(response, f"{self.mass.get_absolute_url()}#piece-row-{piece.pk}",
                             fetch_redirect_response=False)

    def test_with_javascript_the_second_step_comes_as_a_fragment(self):
        response = self.client.get(self.url, {"service": self.mass.pk}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        fragment = response.json()["fragments"]["propose-slot"]
        self.assertIn('<section id="propose-slot"', fragment)
        self.assertIn('id="propose-slot-select"', fragment)
        self.assertNotIn("<html", fragment)


class ProposeFromLibraryBrowserTest(PlaywrightTestCase):
    def test_choosing_a_service_brings_its_slots_and_a_new_slot_can_be_made(self):
        self.login_as_conductor()
        today = timezone.localdate()
        term = make_term(name="Browser Term", start_date=today, end_date=today + timedelta(days=30))
        service = Service.objects.create(term=term, date=today + timedelta(days=3), service_type="Sung Mass")
        ServiceRole.objects.create(service=service, role_name="Communion")
        score = make_score(title="Ave verum corpus", composer_surname="Mozart")
        self.page.goto(f"/scores/{score.pk}/propose/")
        self.page.evaluate("window.__marker = true")
        self.page.select_option("#propose-service", str(service.pk))
        self.page.wait_for_selector("#propose-slot-select")
        assert self.page.evaluate("window.__marker") is True, "the page reloaded"
        assert self.page.is_hidden("#propose-new-slot"), "the new slot's fields showed before New slot… was chosen"
        self.page.select_option("#propose-slot-select", "new")
        assert self.page.is_visible("#propose-new-slot")
        self.page.fill("#id_new-role_name", "After Communion")
        self.page.select_option("#id_new-kind", "motet")
        self.page.click("#propose-form button.btn-primary")
        self.page.wait_for_url(f"**/services/{service.pk}/**")
        slot = ServiceRole.objects.get(service=service, role_name="After Communion")
        assert slot.kind == "motet" and slot.pieces.get().score == score
        assert "Proposed Ave verum corpus (Mozart) for the After Communion." in self.page.inner_text("#toast-region")
