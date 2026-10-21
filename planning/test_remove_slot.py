from datetime import date

from django.test import TestCase

from accounts.testing import make_user
from comments.models import Comment
from library.models import Score

from .models import RolePiece, Service, ServiceRole, Term


class RemoveSlotTests(TestCase):
    def setUp(self):
        self.conductor = make_user("conductor")
        self.client.force_login(self.conductor)
        term = Term.objects.create(name="T", start_date=date(2026, 1, 1), end_date=date(2026, 3, 31), calendar_use="current")
        self.service = Service.objects.create(term=term, date=date(2026, 1, 11), service_type="Sung Mass")
        self.introit = ServiceRole.objects.create(service=self.service, role_name="Introit")
        self.motet = ServiceRole.objects.create(service=self.service, role_name="Offertory motet")
        score = Score.objects.create(title="Ave verum", composer_surname="Byrd")
        piece = RolePiece.objects.create(service_role=self.motet, score=score)
        Comment.objects.create(author=self.conductor, body="Too long?", target=piece)

    def names(self):
        return list(self.service.roles.values_list("role_name", flat=True))

    def test_an_empty_slot_goes_at_once(self):
        response = self.client.post(f"/roles/{self.introit.pk}/remove/", follow=True)
        self.assertEqual(self.names(), ["Offertory motet"])
        self.assertContains(response, "Removed Introit.")

    def test_a_slot_with_pieces_asks_first_without_javascript(self):
        response = self.client.post(f"/roles/{self.motet.pk}/remove/")
        self.assertContains(response, "Remove Offertory motet?")
        self.assertContains(response, "1 proposed piece")
        self.assertContains(response, "1 comment")
        self.assertEqual(self.names(), ["Introit", "Offertory motet"])

        self.client.post(f"/roles/{self.motet.pk}/remove/", {"confirm": "1"})
        self.assertEqual(self.names(), ["Introit"])
        self.assertFalse(RolePiece.objects.exists())
        self.assertFalse(Comment.objects.exists())

    def test_with_javascript_the_list_comes_back(self):
        response = self.client.post(
            f"/roles/{self.motet.pk}/remove/", {"confirm": "1"}, headers={"x-requested-with": "XMLHttpRequest"}
        )
        html = response.json()["fragments"]["roles-list"]
        self.assertIn("Introit", html)
        self.assertNotIn("Offertory motet", html)

    def test_the_page_carries_the_dialog_wording_only_where_pieces_would_go(self):
        response = self.client.get(self.service.get_absolute_url())
        self.assertContains(response, 'data-confirm-title="Remove Offertory motet?"')
        self.assertContains(response, "Its 1 proposed piece, and any comments on it, go with it.")
        self.assertNotContains(response, 'data-confirm-title="Remove Introit?"')

    def test_only_conductors_can_remove(self):
        self.client.force_login(make_user("viewer"))
        self.client.post(f"/roles/{self.introit.pk}/remove/")
        self.assertEqual(self.names(), ["Introit", "Offertory motet"])

    def test_get_is_not_allowed(self):
        self.assertEqual(self.client.get(f"/roles/{self.introit.pk}/remove/").status_code, 405)
