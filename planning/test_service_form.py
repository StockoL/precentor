from datetime import date

from django.test import TestCase

from accounts.testing import make_user
from ordo.models import LiturgicalOccasion
from precentor_project.testing import make_term

from .forms import ServiceForm
from .models import Service


class ServiceFormCalendarTests(TestCase):
    def setUp(self):
        self.term = make_term(
            name="T", start_date=date(2026, 1, 1), end_date=date(2026, 3, 31), calendar_use="historic"
        )
        LiturgicalOccasion.objects.create(name="Epiphany", calendar_use="current", fixed_month=1, fixed_day=6)
        LiturgicalOccasion.objects.create(name="Epiphany", calendar_use="historic", fixed_month=1, fixed_day=6)

    def test_each_occasion_option_names_its_form(self):
        html = str(ServiceForm(instance=Service(term=self.term))["occasion"])
        self.assertIn('data-calendar-use="current"', html)
        self.assertIn('data-calendar-use="historic"', html)

    def test_blank_calendar_names_the_terms(self):
        choices = ServiceForm(instance=Service(term=self.term)).fields["calendar_use"].choices
        self.assertEqual(choices[0], ("", "As the term: Extraordinary Form (1962)"))

    def test_calendar_comes_first_in_the_liturgy_section(self):
        self.client.force_login(make_user("conductor"))
        html = self.client.get(f"/terms/{self.term.pk}/services/add/").content.decode()
        liturgy = html[html.index("<legend>Liturgy</legend>"):]
        self.assertLess(liturgy.index('id="id_calendar_use"'), liturgy.index('id="id_occasion"'))
        self.assertIn("As the term: Extraordinary Form (1962)", html)
