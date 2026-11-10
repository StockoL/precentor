from datetime import date

from django.test import TestCase

from accounts.testing import make_user

from .models import Term


class TermDatesTests(TestCase):
    def setUp(self):
        self.client.force_login(make_user("conductor"))

    def add_term(self, start, end):
        return self.client.post("/terms/add/", {
            "name": "Lent 2027", "start_date": start, "end_date": end, "calendar_use": "current",
        })

    def test_a_term_cant_end_before_it_starts(self):
        response = self.add_term("2027-02-17", "2027-02-16")
        self.assertFormError(response.context["form"], "end_date", "A term can't end before it starts.")
        self.assertFalse(Term.objects.exists())

    def test_a_term_can_start_and_end_on_the_same_day(self):
        self.assertEqual(self.add_term("2027-02-17", "2027-02-17").status_code, 302)
        self.assertEqual(Term.objects.get().end_date, date(2027, 2, 17))
