from urllib.parse import quote

from django.test import TestCase

from accounts.testing import make_organisation, make_user
from library.models import Score
from precentor_project.testing import make_score, make_term

from .models import RolePiece, Service, ServiceRole


class OutsideLibraryTests(TestCase):
    """A reference typed into a slot whose music is usually a score."""

    def setUp(self):
        self.church = make_organisation()
        term = make_term(organisation=self.church)
        self.service = Service.objects.create(term=term, date=term.start_date, service_type="Sung Mass")
        self.kyrie = ServiceRole.objects.create(service=self.service, role_name="Kyrie")
        self.hymn = ServiceRole.objects.create(service=self.service, role_name="Hymn")
        self.missa = RolePiece.objects.create(service_role=self.kyrie, reference="Missa brevis")
        RolePiece.objects.create(service_role=self.hymn, reference="NEH 1")

    def page(self, role):
        self.client.force_login(make_user(role, organisation=self.church))
        return self.client.get(self.service.get_absolute_url())

    def add_link(self):
        back = quote(self.missa.get_absolute_url(), safe="/")
        return f"/library/add/?title=Missa%20brevis&amp;next={back}"

    def test_only_a_reference_in_a_slot_for_scores_is_outside_the_library(self):
        motet = ServiceRole.objects.create(service=self.service, role_name="Motet")
        in_library = RolePiece.objects.create(service_role=motet, score=make_score(organisation=self.church))
        self.assertTrue(self.missa.is_outside_library)
        self.assertFalse(RolePiece.objects.get(reference="NEH 1").is_outside_library)
        self.assertFalse(in_library.is_outside_library)

    def test_the_ordinarys_reference_is_noted_with_a_link_and_the_hymns_isnt(self):
        for role in ("conductor", "librarian"):
            with self.subTest(role=role):
                response = self.page(role)
                self.assertContains(response, "Not in the library.", count=1)
                self.assertContains(response, self.add_link(), count=1)

    def test_a_viewer_sees_the_note_but_not_the_link(self):
        response = self.page("viewer")
        self.assertContains(response, "Not in the library.", count=1)
        self.assertNotContains(response, "/library/add/")

    def test_the_link_fills_in_the_title_and_comes_back_to_the_service(self):
        self.client.force_login(make_user("librarian", organisation=self.church))
        back = self.missa.get_absolute_url()
        response = self.client.get("/library/add/", {"title": "Missa brevis", "next": back})
        self.assertContains(response, 'value="Missa brevis"')
        self.assertContains(response, f'name="next" value="{back}"')
        response = self.client.post("/library/add/", {
            "title": "Missa brevis", "composer_surname": "Palestrina", "copies_owned": 0,
            "soprano_parts": 1, "alto_parts": 1, "tenor_parts": 1, "bass_parts": 1, "next": back,
        })
        self.assertRedirects(response, back, fetch_redirect_response=False)
        self.assertTrue(Score.objects.filter(organisation=self.church, title="Missa brevis").exists())

    def test_without_javascript_the_propose_page_takes_a_reference_for_anything_else(self):
        self.client.force_login(make_user("conductor", organisation=self.church))
        url = f"/roles/{self.kyrie.pk}/pieces/add/"
        self.assertContains(self.client.get(url), "Anything not in the library can be typed here")
        response = self.client.post(url, {"score": "", "reference": "Mass for four voices"})
        piece = RolePiece.objects.get(reference="Mass for four voices")
        self.assertRedirects(response, self.service.get_absolute_url(), fetch_redirect_response=False)
        self.assertIsNone(piece.score)
        self.assertContains(self.client.get(self.service.get_absolute_url()), "Not in the library.", count=2)
