from datetime import date

from django.test import TestCase

from accounts.testing import make_user
from precentor_project.testing import make_score, make_term

from .models import RolePiece, Service, ServiceRole


class PewSheetTestMixin:
    def setUp(self):
        self.viewer = make_user("viewer")
        self.church = self.viewer.organisation
        term = make_term(organisation=self.church)
        self.service = Service.objects.create(term=term, date=date(2026, 1, 11), service_type="Sung Mass")
        self.score = make_score(
            organisation=self.church, title="Ave verum corpus", composer_surname="Byrd", composer_other_names="William",
            text="Ave verum corpus", translation="Hail, true body", translation_credit="Tr. the choir",
        )

    def slot(self, name, **piece):
        slot = ServiceRole.objects.create(service=self.service, role_name=name)
        if piece:
            RolePiece.objects.create(service_role=slot, **piece)
        return slot


class PewSheetRowsTests(PewSheetTestMixin, TestCase):
    def test_only_slots_with_a_confirmed_piece_in_order(self):
        self.slot("Entrance hymn", reference="NEH 1", is_confirmed=True)
        self.slot("Introit", reference="Ad te levavi")  # proposed only
        self.slot("Gradual")  # nothing yet
        self.slot("Offertory motet", score=self.score, is_confirmed=True)
        rows = self.service.pew_sheet_rows()
        self.assertEqual([(row["role_name"], [piece.title for piece in row["pieces"]]) for row in rows], [
            ("Entrance hymn", ["NEH 1"]),
            ("Offertory motet", [str(self.score)]),
        ])

    def test_a_slot_marked_not_needed_is_left_out(self):
        slot = self.slot("Gloria", reference="Missa de Angelis", is_confirmed=True)
        slot.is_not_applicable = True
        slot.save()
        self.assertEqual(self.service.pew_sheet_rows(), [])


class PewSheetPageTests(PewSheetTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.slot("Entrance hymn", reference="NEH 1", is_confirmed=True)
        self.slot("Offertory motet", score=self.score, is_confirmed=True)
        self.client.force_login(self.viewer)
        self.url = f"/services/{self.service.pk}/sheet/"

    def test_a_first_visit_prints_texts_and_composers(self):
        response = self.client.get(self.url)
        self.assertContains(response, '<p class="pew-sheet__piece">NEH 1</p>', html=True)
        self.assertContains(response, '<span class="pew-sheet__composer">William Byrd</span>', html=True)
        self.assertContains(response, '<p class="parallel-text__translation">Hail, true body</p>', html=True)
        self.assertContains(response, "<h2>Offertory motet</h2>", html=True)

    def test_the_options_leave_them_off(self):
        response = self.client.get(self.url, {"shown": "1"})
        self.assertNotContains(response, "pew-sheet__composer")
        self.assertNotContains(response, "Hail, true body")
        self.assertContains(response, "Ave verum corpus")
        response = self.client.get(self.url, {"shown": "1", "texts": "on"})
        self.assertContains(response, "Hail, true body")
        self.assertNotContains(response, "pew-sheet__composer")

    def test_another_churchs_service_is_not_found(self):
        from accounts.testing import make_organisation

        self.client.force_login(make_user("viewer", organisation=make_organisation("St Elsewhere")))
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_the_service_page_links_to_it_for_everyone(self):
        response = self.client.get(self.service.get_absolute_url())
        self.assertContains(response, f'href="{self.url}"')
