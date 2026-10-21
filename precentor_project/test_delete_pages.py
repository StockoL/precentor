from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from library.models import Score
from planning.models import Service, SlotTemplate, Term, TermMarker

User = get_user_model()


class DeleteThenBackTests(TestCase):
    """Deleting, then pressing Back and confirming again, ends on the list
    with a message, never on "Page not found"."""

    def setUp(self):
        self.client.force_login(User.objects.create_superuser(username="admin", password="x"))
        self.term = Term.objects.create(name="T", start_date=date(2026, 1, 1), end_date=date(2026, 3, 31), calendar_use="current")

    def delete_twice(self, url, list_url, message):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])
        self.client.post(url)
        for method in (self.client.get, self.client.post):
            with self.subTest(method=method.__name__):
                response = method(url, follow=True)
                self.assertRedirects(response, list_url)
                self.assertContains(response, message)

    def test_template(self):
        template = SlotTemplate.objects.create(name="Benediction", slot_names="O salutaris")
        self.delete_twice(f"/templates/{template.pk}/delete/", "/templates/", "That template has already been deleted.")

    def test_term_service_and_notice(self):
        service = Service.objects.create(term=self.term, date=date(2026, 1, 11), service_type="Mass")
        notice = TermMarker.objects.create(term=self.term, date=date(2026, 2, 16), text="Half term")
        self.delete_twice(f"/services/{service.pk}/delete/", "/", "That service has already been deleted.")
        self.delete_twice(f"/markers/{notice.pk}/delete/", "/", "That notice has already been deleted.")
        self.delete_twice(f"/terms/{self.term.pk}/delete/", "/", "That term has already been deleted.")

    def test_score(self):
        score = Score.objects.create(title="Ave verum", composer_surname="Byrd")
        self.delete_twice(f"/library/{score.pk}/delete/", "/library/", "That score has already been deleted.")

    def test_permissions_are_still_checked_first(self):
        template = SlotTemplate.objects.create(name="Benediction", slot_names="O salutaris")
        self.client.force_login(User.objects.create_user(username="librarian", password="x"))
        self.assertEqual(self.client.get(f"/templates/{template.pk}/delete/").status_code, 403)


class NotFoundPageTests(TestCase):
    def test_a_missing_page_uses_the_house_style(self):
        self.client.force_login(User.objects.create_superuser(username="admin", password="x"))
        response = self.client.get("/no-such-page/")
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")
        self.assertContains(response, "Page not found", status_code=404)
