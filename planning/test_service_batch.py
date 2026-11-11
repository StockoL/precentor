import re
from datetime import date, timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from accounts.testing import make_organisation, make_user
from precentor_project.test_browser import PlaywrightTestCase
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


class WithCalendarTestCase(BatchTestCase):
    """The real calendar loaded, for the dates' celebrations."""

    @classmethod
    def setUpTestData(cls):
        call_command("load_calendar", stdout=StringIO())

    def boxes(self, response):
        """(date, ticked, disabled, label) for each checkbox, in order."""
        page = response.content.decode()
        found = re.findall(r'<input type="checkbox" name="dates" value="([\d-]+)"[^>]*?( checked)?( disabled)?>\s*'
                           r'<label[^>]*>([^<]*)</label>', page)
        return [(day, bool(ticked), bool(disabled), label) for day, ticked, disabled, label in found]


class PreviewTests(WithCalendarTestCase):

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


class CreateTests(WithCalendarTestCase):
    SUNDAYS = ["2026-11-29", "2026-12-06", "2026-12-13", "2026-12-20"]

    def create(self, dates, **values):
        return self.client.post(self.url, {**self.data(**values), "dates": dates})

    def test_each_ticked_date_gets_a_service_with_its_occasion_type_and_slots(self):
        response = self.create(self.SUNDAYS)
        self.assertRedirects(response, self.term.get_absolute_url(), fetch_redirect_response=False)
        services = list(Service.objects.order_by("date"))
        self.assertEqual([s.date.isoformat() for s in services], self.SUNDAYS)
        first = services[0]
        self.assertEqual((first.service_type, first.occasion.name, first.slot_template, first.calendar_use),
                         ("Mass", "First Sunday of Advent", self.mass, None))
        for service in services:
            self.assertEqual([r.role_name for r in service.roles.all()], ["Introit", "Kyrie", "Gloria", "Communion"])
        self.assertContains(self.client.get(self.term.get_absolute_url()), "Created 4 services.")

    def test_an_unticked_date_is_left_out(self):
        self.create(self.SUNDAYS[:2] + self.SUNDAYS[3:])
        self.assertFalse(Service.objects.filter(date=date(2026, 12, 13)).exists())
        self.assertEqual(Service.objects.count(), 3)

    def test_running_it_twice_makes_no_duplicates(self):
        self.create(self.SUNDAYS)
        Service.objects.filter(date=date(2026, 12, 20)).delete()
        response = self.create(self.SUNDAYS, service_type="mass")
        self.assertEqual(Service.objects.count(), 4)
        self.assertContains(self.client.get(response.url), "Created 1 service; skipped 3 that already exist.")

    def test_a_date_from_outside_the_choices_is_ignored(self):
        self.create(self.SUNDAYS[:1] + ["2026-12-25", "2027-01-03"])
        self.assertEqual([s.date for s in Service.objects.all()], [date(2026, 11, 29)])

    def test_more_than_sixty_is_refused_and_nothing_made(self):
        self.term.end_date = date(2027, 2, 28)
        self.term.save()
        start = date(2026, 11, 29)
        days = [(start + timedelta(days=n)).isoformat() for n in range(61)]
        response = self.create(days, end_date="2027-02-28", pattern="pick")
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "A batch can be up to 60 services; untick some first.", status_code=400)
        self.assertContains(response, ">Create 61 services</button>", status_code=400)
        self.assertFalse(Service.objects.exists())
        self.create(days[:60], end_date="2027-02-28", pattern="pick")
        self.assertEqual(Service.objects.count(), 60)

    def test_nothing_ticked_is_refused(self):
        response = self.create([])
        self.assertContains(response, "Tick at least one date.", status_code=400)

    def test_if_one_fails_none_is_left(self):
        calls = []

        def apply_then_fail(template, service):
            calls.append(service)
            if len(calls) == 2:
                raise RuntimeError("the second one fails")
            return [], []

        with patch.object(SlotTemplate, "apply_to", apply_then_fail), self.assertRaises(RuntimeError):
            self.create(self.SUNDAYS)
        self.assertFalse(Service.objects.exists())

    def test_a_viewer_cant_create(self):
        self.client.force_login(make_user("viewer", organisation=self.church))
        self.assertEqual(self.create(self.SUNDAYS).status_code, 403)
        self.assertFalse(Service.objects.exists())

    def test_another_churchs_term_is_not_found(self):
        theirs = make_term(organisation=make_organisation("St Elsewhere"))
        response = self.client.post(f"/terms/{theirs.pk}/services/batch/", {**self.data(), "dates": self.SUNDAYS})
        self.assertEqual(response.status_code, 404)

    def test_without_javascript_step_by_step(self):
        first = self.client.get(self.url)
        self.assertContains(first, 'method="get"')
        preview = self.step_one(pattern="sundays_and_solemnities")
        ticked = [day for day, is_ticked, _, _ in self.boxes(preview) if is_ticked]
        self.assertRedirects(self.create(ticked, pattern="sundays_and_solemnities"), self.term.get_absolute_url())
        self.assertEqual(Service.objects.get(date=date(2026, 12, 8)).occasion.name,
                         "The Immaculate Conception of the Blessed Virgin Mary")


class BatchBrowserTest(PlaywrightTestCase):
    def test_select_all_none_and_the_count_follow_the_ticks(self):
        call_command("load_calendar", stdout=StringIO())
        self.login_as_conductor()
        term = make_term(name="Advent 2026", start_date=date(2026, 11, 29), end_date=date(2026, 12, 24))
        mass = make_slot_template(name="Mass", slots=("Introit", "Kyrie"))
        Service.objects.create(term=term, date=date(2026, 12, 6), service_type="Mass")
        self.page.goto(f"/terms/{term.pk}/services/batch/?template={mass.pk}&service_type=&start_date=2026-11-29"
                       "&end_date=2026-12-24&pattern=sundays")
        button = "#batch-create"
        assert self.page.inner_text(button) == "Create 3 services"
        self.page.click("text=Select none")
        assert self.page.inner_text(button) == "Create 0 services"
        self.page.check("#batch-date-2026-12-13")
        assert self.page.inner_text(button) == "Create 1 service"
        self.page.click("text=Select all")
        assert self.page.inner_text(button) == "Create 3 services"
        # The date that already has a Mass stays as it was.
        assert self.page.is_disabled("#batch-date-2026-12-06") and not self.page.is_checked("#batch-date-2026-12-06")
