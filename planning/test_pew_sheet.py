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
