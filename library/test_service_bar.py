from datetime import date

from django.test import TestCase

from accounts.testing import make_organisation, make_user
from ordo.models import LiturgicalOccasion
from planning.models import RolePiece, Service, ServiceRole
from precentor_project.testing import make_score, make_term


class ServiceBarTestCase(TestCase):
    """A Sung Mass on Michaelmas with a Credo, and Credo III in the library."""

    def setUp(self):
        self.church = make_organisation()
        self.client.force_login(make_user("conductor", organisation=self.church))
        term = make_term(organisation=self.church, start_date=date(2026, 9, 1), end_date=date(2026, 12, 20))
        michaelmas = LiturgicalOccasion.objects.create(name="Michaelmas", key="test:michaelmas", calendar_use="current")
        self.service = Service.objects.create(term=term, date=date(2026, 11, 1), service_type="Sung Mass",
                                              occasion=michaelmas)
        self.credo = ServiceRole.objects.create(service=self.service, role_name="Credo")
        self.score = make_score(organisation=self.church, title="Credo III", composer_surname="Plainchant")

    def page(self, service_pk):
        return self.client.get(f"/library/{self.score.pk}/?service={service_pk}")


class ServiceBarTests(ServiceBarTestCase):
    """A score opened from a service says where it sits in that service."""

    def test_the_bar_names_the_slot_the_day_and_the_state(self):
        RolePiece.objects.create(service_role=self.credo, score=self.score)
        response = self.page(self.service.pk)
        self.assertContains(response, "<span>Proposed for the Credo, Sunday 1 November (Michaelmas)</span>", html=True)
        self.assertContains(response, f'<a href="{self.service.get_absolute_url()}">Back to the service</a>', html=True)

    def test_each_slot_of_that_service_is_listed_in_order(self):
        offertory = ServiceRole.objects.create(service=self.service, role_name="Offertory")
        RolePiece.objects.create(service_role=offertory, score=self.score, is_confirmed=True)
        RolePiece.objects.create(service_role=self.credo, score=self.score)
        page = self.page(self.service.pk).content.decode()
        credo = page.index("Proposed for the Credo")
        offertory = page.index("Confirmed for the Offertory, Sunday 1 November (Michaelmas)")
        self.assertLess(credo, offertory)

    def test_another_churchs_service_is_ignored(self):
        RolePiece.objects.create(service_role=self.credo, score=self.score)
        theirs = make_term(organisation=make_organisation("St Elsewhere"), start_date=date(2026, 9, 1),
                           end_date=date(2026, 12, 20))
        their_service = Service.objects.create(term=theirs, date=date(2026, 11, 1), service_type="Sung Mass")
        for value in (their_service.pk, 999999, "abc", ""):
            with self.subTest(service=value):
                response = self.page(value)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Credo III")
                self.assertNotContains(response, "service-context")
                self.assertNotContains(response, "Back to the service")

    def test_no_bar_without_a_service(self):
        RolePiece.objects.create(service_role=self.credo, score=self.score)
        self.assertNotContains(self.client.get(f"/library/{self.score.pk}/"), "service-context")


class BarActionsTests(ServiceBarTestCase):
    """Confirm and Remove on the bar, coming back to the score's page."""

    def setUp(self):
        super().setUp()
        self.piece = RolePiece.objects.create(service_role=self.credo, score=self.score)
        self.here = f"/library/{self.score.pk}/?service={self.service.pk}"

    def test_those_who_plan_get_confirm_and_remove_that_come_back_here(self):
        page = self.client.get(self.here)
        self.assertContains(page, f'action="/pieces/{self.piece.pk}/toggle-confirm/"')
        self.assertContains(page, f'action="/pieces/{self.piece.pk}/remove/"')
        self.assertContains(page, f'name="next" value="{self.here}"', count=2)
        self.client.force_login(make_user("viewer", organisation=self.church))
        page = self.client.get(self.here)
        self.assertContains(page, "Proposed for the Credo")
        self.assertNotContains(page, "/toggle-confirm/")
        self.assertNotContains(page, f"/pieces/{self.piece.pk}/remove/")

    def test_confirm_comes_back_to_the_score(self):
        response = self.client.post(f"/pieces/{self.piece.pk}/toggle-confirm/", {"confirmed": "1", "next": self.here})
        self.assertRedirects(response, self.here)
        self.piece.refresh_from_db()
        self.assertTrue(self.piece.is_confirmed)
        self.assertContains(self.client.get(self.here), "Confirmed for the Credo")

    def test_remove_comes_back_to_the_score_with_its_message(self):
        response = self.client.post(f"/pieces/{self.piece.pk}/remove/", {"next": self.here}, follow=True)
        self.assertRedirects(response, self.here)
        self.assertContains(response, "Removed Credo III (Plainchant) from the Credo.")
        self.assertFalse(RolePiece.objects.filter(pk=self.piece.pk).exists())

    def test_a_confirmed_piece_asks_first_and_still_comes_back(self):
        self.piece.is_confirmed = True
        self.piece.save()
        page = self.client.post(f"/pieces/{self.piece.pk}/remove/", {"next": self.here})
        self.assertContains(page, f'name="next" value="{self.here}"')
        self.assertContains(page, f'<a class="btn-ghost" href="{self.here}">Cancel</a>', html=True)
        response = self.client.post(f"/pieces/{self.piece.pk}/remove/", {"next": self.here, "confirm": "1"})
        self.assertRedirects(response, self.here)

    def test_another_sites_address_goes_to_the_service_instead(self):
        elsewhere = "https://example.com/"
        response = self.client.post(f"/pieces/{self.piece.pk}/toggle-confirm/", {"confirmed": "1", "next": elsewhere})
        self.assertRedirects(response, self.service.get_absolute_url())
        response = self.client.post(f"/pieces/{self.piece.pk}/remove/", {"next": elsewhere, "confirm": "1"})
        self.assertRedirects(response, self.service.get_absolute_url())
