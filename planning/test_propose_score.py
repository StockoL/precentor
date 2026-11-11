import re
from datetime import timedelta

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from accounts.testing import make_organisation, make_user
from ordo.models import UseType
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


class ChooseASlotTests(ProposeFromLibraryTestCase):
    def setUp(self):
        super().setUp()
        self.mass = self.service(7)
        self.introit = ServiceRole.objects.create(service=self.mass, role_name="Introit")
        RolePiece.objects.create(service_role=self.introit, reference="Ad te levavi")
        self.offertory = ServiceRole.objects.create(service=self.mass, role_name="Offertory")
        self.communion = ServiceRole.objects.create(service=self.mass, role_name="Communion")

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
