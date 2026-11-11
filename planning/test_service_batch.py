import re
from datetime import date
from io import StringIO

from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from accounts.testing import make_organisation, make_user
from precentor_project.testing import make_slot_template, make_term

from .forms import ServiceBatchForm
from .models import Service, SlotTemplate


class BatchTestCase(TestCase):
    def setUp(self):
        self.church = make_organisation()
        self.client.force_login(make_user("conductor", organisation=self.church))
        self.term = make_term(organisation=self.church, name="Advent 2026",
                              start_date=date(2026, 11, 29), end_date=date(2026, 12, 24))
        self.mass = make_slot_template(organisation=self.church, name="Mass",
                                       slots=("Introit", "Kyrie", "Gloria", "Communion"))
        self.url = f"/terms/{self.term.pk}/services/batch/"

    def data(self, **values):
        return {"template": self.mass.pk, "service_type": "", "start_date": "2026-11-29", "end_date": "2026-12-24",
                "pattern": "sundays", **values}

    def step_one(self, **values):
        return self.client.get(self.url, self.data(**values))

    def form(self, **values):
        return ServiceBatchForm(self.data(**values), term=self.term)


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
        form = self.form()
        self.assertTrue(form.is_valid(), form.errors)
        self.assertTemplateUsed(self.step_one(), "planning/service_batch_preview.html")

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
        form = self.form()
        form.is_valid()
        self.assertEqual(form.cleaned_data["service_type"], "Mass")
        form = self.form(service_type="Sung Mass")
        form.is_valid()
        self.assertEqual(form.cleaned_data["service_type"], "Sung Mass")


class PreviewTests(BatchTestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_calendar", stdout=StringIO())

    def boxes(self, response):
        """(date, ticked, disabled, label) for each checkbox, in order."""
        page = response.content.decode()
        found = re.findall(r'<input type="checkbox" name="dates" value="([\d-]+)"[^>]*?( checked)?( disabled)?>\s*'
                           r'<label[^>]*>([^<]*)</label>', page)
        return [(day, bool(ticked), bool(disabled), label) for day, ticked, disabled, label in found]

    def test_every_sunday_ticked_with_its_name_and_the_count(self):
        response = self.step_one()
        self.assertEqual(self.boxes(response), [
            ("2026-11-29", True, False, "Sun 29 Nov: First Sunday of Advent"),
            ("2026-12-06", True, False, "Sun 6 Dec: Second Sunday of Advent"),
            ("2026-12-13", True, False, "Sun 13 Dec: Third Sunday of Advent"),
            ("2026-12-20", True, False, "Sun 20 Dec: Fourth Sunday of Advent"),
        ])
        self.assertContains(response, ">Create 4 services</button>")
        self.assertFalse(Service.objects.exists())

    def test_the_second_pattern_adds_the_weekday_solemnity(self):
        days = [day for day, ticked, _, _ in self.boxes(self.step_one(pattern="sundays_and_solemnities")) if ticked]
        self.assertIn("2026-12-08", days)
        self.assertEqual(len(days), 5)

    def test_picking_lists_every_date_by_month_none_ticked(self):
        response = self.step_one(pattern="pick")
        boxes = self.boxes(response)
        self.assertEqual(len(boxes), 26)
        self.assertFalse(any(ticked for _, ticked, _, _ in boxes))
        self.assertContains(response, "<legend>November 2026</legend>", html=True)
        self.assertContains(response, "<legend>December 2026</legend>", html=True)
        self.assertContains(response, ">Create 0 services</button>")

    def test_a_date_that_already_has_one_is_shown_but_not_offered(self):
        Service.objects.create(term=self.term, date=date(2026, 12, 6), service_type="mass")
        response = self.step_one()
        self.assertIn(("2026-12-06", False, True, "Sun 6 Dec: Second Sunday of Advent (already has a Mass)"),
                      self.boxes(response))
        self.assertContains(response, ">Create 3 services</button>")

    def test_change_goes_back_to_step_one_filled_in(self):
        response = self.step_one(pattern="pick", change="1")
        self.assertTemplateUsed(response, "planning/service_batch.html")
        self.assertEqual(response.context["form"]["pattern"].value(), "pick")

    def test_the_preview_costs_the_same_however_long_the_range(self):
        with CaptureQueriesContext(connection) as week:
            self.step_one(end_date="2026-12-05", pattern="pick")
        with CaptureQueriesContext(connection) as term:
            self.step_one(pattern="pick")
        self.assertEqual(len(term), len(week))
