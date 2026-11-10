from datetime import date

from django.test import TestCase

from accounts.testing import make_user
from precentor_project.testing import make_term

from .models import Service, Term


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


class ServiceDateTests(TestCase):
    def setUp(self):
        user = make_user("conductor")
        self.client.force_login(user)
        self.term = make_term(organisation=user.organisation, name="Lent 2027",
                              start_date=date(2027, 2, 17), end_date=date(2027, 4, 3))
        self.message = "Lent 2027 runs from Wed 17 Feb 2027 to Sat 3 Apr 2027, so the service needs a date in between."

    def add_service(self, day):
        return self.client.post(f"/terms/{self.term.pk}/services/add/", {
            "date": day, "service_type": "Sung Mass", "calendar_use": "",
        })

    def test_a_date_outside_the_term_is_refused_naming_its_dates(self):
        for day in ("2027-02-16", "2027-04-04"):
            with self.subTest(day=day):
                self.assertFormError(self.add_service(day).context["form"], "date", self.message)
        self.assertFalse(Service.objects.exists())

    def test_the_terms_first_and_last_days_are_allowed(self):
        for day in ("2027-02-17", "2027-04-03"):
            with self.subTest(day=day):
                self.assertEqual(self.add_service(day).status_code, 302)
        self.assertEqual(Service.objects.count(), 2)

    def test_editing_a_service_checks_its_own_term(self):
        service = Service.objects.create(term=self.term, date=date(2027, 2, 21), service_type="Sung Mass")
        response = self.client.post(f"/services/{service.pk}/edit/", {
            "date": "2027-05-02", "service_type": "Sung Mass", "calendar_use": "",
        })
        self.assertFormError(response.context["form"], "date", self.message)
        service.refresh_from_db()
        self.assertEqual(service.date, date(2027, 2, 21))


class TermStrandingTests(TestCase):
    def setUp(self):
        user = make_user("conductor")
        self.client.force_login(user)
        self.term = make_term(organisation=user.organisation, name="Lent 2027",
                              start_date=date(2027, 2, 17), end_date=date(2027, 4, 3))
        for day in (date(2027, 2, 21), date(2027, 3, 28), date(2027, 4, 3)):
            Service.objects.create(term=self.term, date=day, service_type="Sung Mass")
        self.url = f"/terms/{self.term.pk}/edit/"

    def edit(self, name="Lent 2027", start="2027-02-17", end="2027-04-03"):
        return self.client.post(self.url, {
            "name": name, "start_date": start, "end_date": end, "calendar_use": self.term.calendar_use,
        })

    def assertUnchanged(self):
        self.term.refresh_from_db()
        self.assertEqual((self.term.start_date, self.term.end_date), (date(2027, 2, 17), date(2027, 4, 3)))

    def test_an_earlier_end_naming_how_many_and_the_first(self):
        form = self.edit(end="2027-03-27").context["form"]
        self.assertFormError(form, "end_date", "2 services would fall outside these dates, "
                                               "the first on Sun 28 Mar 2027. Move or delete them first.")
        self.assertUnchanged()

    def test_a_later_start_beside_the_start(self):
        form = self.edit(start="2027-02-22").context["form"]
        self.assertFormError(form, "start_date", "A service on Sun 21 Feb 2027 would fall outside these dates. "
                                                 "Move or delete it first.")
        self.assertUnchanged()

    def test_both_dates_changed_says_so_above_them(self):
        form = self.edit(start="2027-02-22", end="2027-03-27").context["form"]
        self.assertIn("3 services would fall outside", form.non_field_errors()[0])
        self.assertUnchanged()

    def test_dates_on_the_first_and_last_services_are_allowed(self):
        self.assertEqual(self.edit(start="2027-02-21", end="2027-04-03").status_code, 302)
        self.term.refresh_from_db()
        self.assertEqual(self.term.start_date, date(2027, 2, 21))

    def test_renaming_a_term_with_services_already_outside_it(self):
        Service.objects.create(term=self.term, date=date(2027, 5, 2), service_type="Sung Mass")
        self.assertEqual(self.edit(name="Lent and Easter 2027").status_code, 302)
        self.term.refresh_from_db()
        self.assertEqual(self.term.name, "Lent and Easter 2027")
