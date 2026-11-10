from datetime import date

from django.test import TestCase

from accounts.testing import make_organisation, make_user
from precentor_project.testing import make_score, make_term

from .models import RolePiece, Service, ServiceRole


class ViewersSeeWorkInProgressTests(TestCase):
    """
    Viewers are read-only members who can comment, and commenting on a
    draft needs sight of it: they see the draft music list and the pew
    sheet, and from the term page each service's status and its proposed
    pieces, but change nothing. Nobody else sees any of it.
    """

    def setUp(self):
        self.church = make_organisation()
        term = make_term(organisation=self.church, start_date=date(2027, 2, 17), end_date=date(2027, 4, 3))
        self.service = Service.objects.create(term=term, date=date(2027, 2, 21), service_type="Sung Mass")
        slot = ServiceRole.objects.create(service=self.service, role_name="Offertory motet")
        RolePiece.objects.create(service_role=slot, score=make_score(organisation=self.church, title="Ave verum"))
        self.term = term
        self.draft = f"/terms/{term.pk}/music-list/?draft=1"
        self.sheet = f"/services/{self.service.pk}/sheet/"

    def test_a_viewer_sees_the_draft_and_the_proposed_piece_as_proposed(self):
        self.client.force_login(make_user("viewer", organisation=self.church))
        term_page = self.client.get(self.term.get_absolute_url())
        self.assertContains(term_page, "In progress")
        self.assertContains(term_page, f'href="/terms/{self.term.pk}/music-list/"')
        draft = self.client.get(self.draft)
        self.assertContains(draft, "DRAFT")
        # Nothing confirmed yet, so the slot is shown as still to come.
        self.assertContains(draft, "Offertory motet")
        self.assertContains(draft, "TBC")
        self.assertEqual(self.client.get(self.sheet).status_code, 200)
        service_page = self.client.get(self.service.get_absolute_url())
        self.assertContains(service_page, "Ave verum")
        self.assertContains(service_page, '<span class="badge badge--proposed">', html=False)
        self.assertNotContains(service_page, "confirm-toggle-")

    def test_signed_out_visitors_go_to_sign_in(self):
        for url in (self.draft, self.sheet):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith("/accounts/login/"))

    def test_another_churchs_member_gets_not_found(self):
        self.client.force_login(make_user("conductor", organisation=make_organisation("St Elsewhere")))
        for url in (self.draft, self.sheet):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)
