from datetime import date

from django.test import TestCase

from accounts.testing import make_organisation, make_user
from library.models import Hymnal, HymnEntry
from precentor_project.testing import make_score, make_term

from .models import RolePiece, Service, ServiceRole


class PieceLinkTests(TestCase):
    """A piece's title links to its score or its hymn, carrying the service."""

    def setUp(self):
        self.church = make_organisation()
        self.client.force_login(make_user("conductor", organisation=self.church))
        term = make_term(organisation=self.church, start_date=date(2026, 9, 1), end_date=date(2026, 12, 20))
        self.service = Service.objects.create(term=term, date=date(2026, 11, 1), service_type="Sung Mass")
        self.credo = ServiceRole.objects.create(service=self.service, role_name="Credo")
        self.hymn_slot = ServiceRole.objects.create(service=self.service, role_name="Hymn", kind="hymn")
        self.score = make_score(organisation=self.church, title="Credo III", composer_surname="Plainchant")
        neh = Hymnal.objects.create(organisation=self.church, name="New English Hymnal", short_name="NEH")
        self.entry = HymnEntry.find_or_make(neh, "53")
        self.scored = RolePiece.objects.create(service_role=self.credo, score=self.score)
        self.hymn = RolePiece.objects.create(service_role=self.hymn_slot, hymn_entry=self.entry)
        self.typed = RolePiece.objects.create(service_role=self.credo, reference="Credo I")

    def page(self):
        return self.client.get(self.service.get_absolute_url())

    def test_a_score_links_to_its_page_with_the_service(self):
        self.assertEqual(self.scored.link_url, f"/library/{self.score.pk}/?service={self.service.pk}")
        url = f"/library/{self.score.pk}/?service={self.service.pk}"
        self.assertContains(self.page(), f'<a href="{url}">Credo III (Plainchant)</a>', html=True)

    def test_a_hymn_links_to_its_hymns_page_with_the_service(self):
        url = f"/library/hymns/{self.entry.hymn_id}/?service={self.service.pk}"
        self.assertEqual(self.hymn.link_url, url)
        self.assertContains(self.page(), f'<a href="{url}">NEH 53</a>', html=True)

    def test_a_typed_reference_links_nowhere(self):
        self.assertEqual(self.typed.link_url, "")
        row = self.page().content.decode().split(f'id="piece-row-{self.typed.pk}"')[1].split("</li>")[0]
        self.assertIn("Credo I", row)
        self.assertNotIn("<a href=\"/library/", row.split("badge")[0])
