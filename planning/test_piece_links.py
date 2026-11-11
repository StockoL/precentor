import re
from datetime import date

from django.test import TestCase

from accounts.testing import make_organisation, make_user
from library.models import Hymnal, HymnEntry
from precentor_project.test_browser import PlaywrightTestCase
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


class MusicListLinkTests(TestCase):
    """The on-screen music list links each confirmed piece; the words stay the same."""

    def setUp(self):
        self.church = make_organisation()
        self.client.force_login(make_user("conductor", organisation=self.church))
        self.term = make_term(organisation=self.church, start_date=date(2026, 9, 1), end_date=date(2026, 12, 20))
        self.service = Service.objects.create(term=self.term, date=date(2026, 11, 1), service_type="Sung Mass")
        credo = ServiceRole.objects.create(service=self.service, role_name="Credo")
        hymn_slot = ServiceRole.objects.create(service=self.service, role_name="Hymn", kind="hymn")
        self.score = make_score(organisation=self.church, title="Credo III", composer_surname="Plainchant")
        neh = Hymnal.objects.create(organisation=self.church, name="New English Hymnal", short_name="NEH")
        self.entry = HymnEntry.find_or_make(neh, "53")
        RolePiece.objects.create(service_role=credo, score=self.score, is_confirmed=True)
        RolePiece.objects.create(service_role=credo, reference="Credo I", is_confirmed=True)
        RolePiece.objects.create(service_role=hymn_slot, hymn_entry=self.entry, is_confirmed=True)
        self.url = f"/terms/{self.term.pk}/music-list/"

    def test_scores_and_hymns_link_and_a_reference_does_not(self):
        page = self.client.get(self.url)
        service = f"?service={self.service.pk}"
        self.assertContains(page, f'<a href="/library/{self.score.pk}/{service}">Credo III (Plainchant)</a>', html=True)
        self.assertContains(page, f'<a href="/library/hymns/{self.entry.hymn_id}/{service}">NEH 53</a>', html=True)
        self.assertNotContains(page, ">Credo I</a>")

    def test_the_words_are_as_before(self):
        page = self.client.get(self.url).content.decode()
        lines = [re.sub(r"<[^>]+>", "", dd).strip() for dd in re.findall(r"<dd[^>]*>(.*?)</dd>", page, re.S)]
        self.assertEqual(lines, ["Credo III (Plainchant), Credo I", "NEH 53"])

    def test_the_links_cost_no_query_per_piece(self):
        self.client.get(self.url)
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as before:
            self.client.get(self.url)
        for n in range(4):
            slot = ServiceRole.objects.create(service=self.service, role_name=f"Motet {n}")
            RolePiece.objects.create(service_role=slot, score=make_score(organisation=self.church, title=f"Motet {n}"),
                                     is_confirmed=True)
        with self.assertNumQueries(len(before)):
            self.client.get(self.url)

    def test_the_pew_sheet_has_no_links_to_the_pieces(self):
        sheet = self.client.get(f"/services/{self.service.pk}/sheet/")
        self.assertContains(sheet, "Credo III")
        self.assertNotContains(sheet, f'href="/library/{self.score.pk}/')
        self.assertNotContains(sheet, "?service=")


class PrintedLinkBrowserTest(PlaywrightTestCase):
    def test_a_printed_title_looks_like_the_words_around_it(self):
        self.login_as_conductor()
        term = make_term(name="Browser Term", start_date=date(2026, 1, 1), end_date=date(2026, 3, 31))
        service = Service.objects.create(term=term, date=date(2026, 1, 11), service_type="Sung Mass")
        slot = ServiceRole.objects.create(service=service, role_name="Credo")
        RolePiece.objects.create(service_role=slot, score=make_score(title="Credo III"), is_confirmed=True)
        self.page.goto(f"/terms/{term.pk}/music-list/")
        link = ".service-entry dd a"
        self.page.wait_for_selector(link)
        on_screen = self.page.eval_on_selector(link, "a => getComputedStyle(a).textDecorationLine")
        self.page.emulate_media(media="print")
        printed = self.page.eval_on_selector(link, """a => {
            const style = getComputedStyle(a), around = getComputedStyle(a.closest('dd'));
            return [style.textDecorationLine, style.color === around.color,
                    getComputedStyle(a, '::after').content];
        }""")
        self.assertEqual(on_screen, "underline")
        self.assertEqual(printed, ["none", True, "none"])
