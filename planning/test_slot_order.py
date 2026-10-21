from datetime import date

from django.test import TestCase

from accounts.testing import make_user

from .models import Service, ServiceRole, Term


class SlotOrderTests(TestCase):
    def setUp(self):
        self.client.force_login(make_user("conductor"))
        term = Term.objects.create(name="T", start_date=date(2026, 1, 1), end_date=date(2026, 3, 31), calendar_use="current")
        self.service = Service.objects.create(term=term, date=date(2026, 1, 11), service_type="Sung Mass")
        self.roles = [ServiceRole.objects.create(service=self.service, role_name=n) for n in ("Introit", "Gloria", "Communion")]

    def names(self):
        return list(self.service.roles.values_list("role_name", flat=True))

    def test_a_new_slot_goes_at_the_end(self):
        ServiceRole.objects.create(service=self.service, role_name="Recessional")
        self.assertEqual(self.names(), ["Introit", "Gloria", "Communion", "Recessional"])

    def test_move_up_and_down(self):
        motet = ServiceRole.objects.create(service=self.service, role_name="Offertory motet")
        for _ in range(2):
            self.client.post(f"/roles/{motet.pk}/move/", {"direction": "up"})
        self.assertEqual(self.names(), ["Introit", "Offertory motet", "Gloria", "Communion"])
        self.client.post(f"/roles/{motet.pk}/move/", {"direction": "down"})
        self.assertEqual(self.names(), ["Introit", "Gloria", "Offertory motet", "Communion"])

    def test_moving_past_either_end_does_nothing(self):
        self.client.post(f"/roles/{self.roles[0].pk}/move/", {"direction": "up"})
        self.client.post(f"/roles/{self.roles[2].pk}/move/", {"direction": "down"})
        self.assertEqual(self.names(), ["Introit", "Gloria", "Communion"])

    def test_without_javascript_it_goes_back_to_the_service(self):
        response = self.client.post(f"/roles/{self.roles[1].pk}/move/", {"direction": "up"})
        self.assertRedirects(response, self.service.get_absolute_url())

    def test_with_javascript_it_returns_the_redrawn_list(self):
        response = self.client.post(
            f"/roles/{self.roles[1].pk}/move/", {"direction": "up"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        html = response.json()["fragments"]["roles-list"]
        self.assertLess(html.index("Gloria"), html.index("Introit"))

    def test_a_drag_sets_the_whole_order(self):
        pks = [self.roles[2].pk, self.roles[0].pk, self.roles[1].pk]
        self.client.post(f"/services/{self.service.pk}/slots/order/", {"order": ",".join(map(str, pks))})
        self.assertEqual(self.names(), ["Communion", "Introit", "Gloria"])

    def test_an_order_that_does_not_match_the_slots_changes_nothing(self):
        for bad in (f"{self.roles[0].pk}", "1,2,3,4", "a,b", ""):
            with self.subTest(order=bad):
                response = self.client.post(
                    f"/services/{self.service.pk}/slots/order/", {"order": bad}, HTTP_X_REQUESTED_WITH="XMLHttpRequest"
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(self.names(), ["Introit", "Gloria", "Communion"])

    def test_only_a_conductor_moves_slots(self):
        self.client.force_login(make_user("librarian"))
        response = self.client.post(f"/roles/{self.roles[2].pk}/move/", {"direction": "up"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.names(), ["Introit", "Gloria", "Communion"])
