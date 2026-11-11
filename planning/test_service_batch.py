from datetime import date

from django.test import TestCase

from accounts.testing import make_organisation, make_user
from precentor_project.testing import make_slot_template, make_term

from .models import SlotTemplate


class BatchTestCase(TestCase):
    def setUp(self):
        self.church = make_organisation()
        self.client.force_login(make_user("conductor", organisation=self.church))
        self.term = make_term(organisation=self.church, name="Advent 2026",
                              start_date=date(2026, 11, 29), end_date=date(2026, 12, 24))
        self.mass = make_slot_template(organisation=self.church, name="Mass",
                                       slots=("Introit", "Kyrie", "Gloria", "Communion"))
        self.url = f"/terms/{self.term.pk}/services/batch/"

    def step_one(self, **values):
        data = {"template": self.mass.pk, "service_type": "", "start_date": "2026-11-29", "end_date": "2026-12-24",
                "pattern": "sundays", **values}
        return self.client.get(self.url, data)


class StepOneTests(BatchTestCase):
    def test_the_term_page_offers_it_to_those_who_plan(self):
        self.assertContains(self.client.get(self.term.get_absolute_url()),
                            f'<a class="btn" href="{self.url}">Add several services</a>', html=True)
        self.client.force_login(make_user("viewer", organisation=self.church))
        self.assertNotContains(self.client.get(self.term.get_absolute_url()), "Add several services")

    def test_a_viewer_is_refused_and_another_churchs_term_is_not_found(self):
        theirs = make_term(organisation=make_organisation("St Elsewhere"))
        self.assertEqual(self.client.get(f"/terms/{theirs.pk}/services/batch/").status_code, 404)
        self.client.force_login(make_user("viewer", organisation=self.church))
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_it_starts_with_the_terms_dates_and_this_churchs_templates(self):
        SlotTemplate.objects.create(organisation=make_organisation("St Elsewhere"), name="Their template")
        form = self.client.get(self.url).context["form"]
        dates = (form["start_date"].value(), form["end_date"].value())
        self.assertEqual(dates, (self.term.start_date, self.term.end_date))
        self.assertEqual(form["pattern"].value(), "sundays")
        self.assertNotIn("Their template", [str(t) for t in form.fields["template"].queryset])
        self.assertEqual(form.fields["pattern"].choices[1][1], "Sundays and solemnities")

    def test_the_terms_own_first_and_last_days_are_allowed(self):
        form = self.step_one().context["form"]
        self.assertTrue(form.is_valid(), form.errors)

    def test_dates_outside_the_term_are_refused_at_either_end(self):
        message = ("Advent 2026 runs from Sun 29 Nov 2026 to Thu 24 Dec 2026, "
                   "so the dates need to be in between.")
        form = self.step_one(start_date="2026-11-28", end_date="2026-12-25").context["form"]
        self.assertEqual(form.errors["start_date"], [message])
        self.assertEqual(form.errors["end_date"], [message])

    def test_a_range_cant_end_before_it_starts(self):
        form = self.step_one(start_date="2026-12-10", end_date="2026-12-01").context["form"]
        self.assertEqual(form.errors["end_date"], ["The range can't end before it starts."])

    def test_the_type_is_the_templates_name_unless_given(self):
        form = self.step_one().context["form"]
        form.is_valid()
        self.assertEqual(form.cleaned_data["service_type"], "Mass")
        form = self.step_one(service_type="Sung Mass").context["form"]
        form.is_valid()
        self.assertEqual(form.cleaned_data["service_type"], "Sung Mass")
