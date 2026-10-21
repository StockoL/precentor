from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase

from .forms import SlotTemplateForm
from .models import Service, ServiceRole, SlotTemplate, Term

User = get_user_model()

MASS = ["Introit", "Kyrie", "Gloria", "Gradual", "Alleluia or Tract", "Credo", "Offertory", "Sanctus", "Agnus Dei", "Communion"]


class TemplateTestMixin:
    def setUp(self):
        self.conductor = User.objects.create_user(username="conductor", password="testpass123")
        self.conductor.groups.add(Group.objects.get_or_create(name="Conductor")[0])
        self.client.force_login(self.conductor)
        term = Term.objects.create(name="T", start_date=date(2026, 1, 1), end_date=date(2026, 3, 31), calendar_use="current")
        self.service = Service.objects.create(term=term, date=date(2026, 1, 11), service_type="Sung Mass")
        self.mass = SlotTemplate.objects.get(name="Mass")

    def slot_names(self):
        return list(self.service.roles.values_list("role_name", flat=True))


class ReadyMadeTemplateTests(TestCase):
    def test_mass_and_vespers_come_ready_made(self):
        self.assertEqual(SlotTemplate.objects.get(name="Mass").slots, MASS)
        self.assertEqual(SlotTemplate.objects.get(name="Vespers").slots, ["Psalms", "Hymn", "Magnificat", "Marian antiphon"])


class SlotParsingTests(TestCase):
    def test_lines_are_trimmed_blanks_dropped_and_each_name_kept_once(self):
        template = SlotTemplate(slot_names="  Introit \n\nKyrie\nkyrie\n  Offertory   motet  ")
        self.assertEqual(template.slots, ["Introit", "Kyrie", "Offertory motet"])


class ApplyTemplateTests(TemplateTestMixin, TestCase):
    def test_adds_the_slots_in_order(self):
        added, already = self.mass.apply_to(self.service)
        self.assertEqual(self.slot_names(), MASS)
        self.assertEqual((added, already), (MASS, []))

    def test_leaves_out_slots_the_service_already_has_and_twice_adds_nothing(self):
        ServiceRole.objects.create(service=self.service, role_name="kyrie")
        added, already = self.mass.apply_to(self.service)
        self.assertEqual(already, ["Kyrie"])
        self.assertEqual(len(self.slot_names()), len(MASS))
        self.assertEqual(self.mass.apply_to(self.service), ([], MASS))
        self.assertEqual(len(self.slot_names()), len(MASS))

    def test_the_button_applies_it_and_says_what_was_added(self):
        url = f"/services/{self.service.pk}/templates/{self.mass.pk}/apply/"
        response = self.client.post(url, follow=True)
        self.assertRedirects(response, self.service.get_absolute_url())
        self.assertContains(response, "Added 10 slots from Mass.")
        response = self.client.post(url, follow=True)
        self.assertContains(response, "The Mass slots are all here already.")

    def test_only_a_conductor_can_apply_one_and_only_by_post(self):
        url = f"/services/{self.service.pk}/templates/{self.mass.pk}/apply/"
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.force_login(User.objects.create_user(username="librarian", password="x"))
        self.client.post(url)
        self.assertEqual(self.slot_names(), [])

    def test_the_service_page_offers_each_template(self):
        response = self.client.get(self.service.get_absolute_url())
        self.assertContains(response, "Add slots from a template")
        for template in SlotTemplate.objects.all():
            with self.subTest(template=template.name):
                self.assertContains(response, f"/services/{self.service.pk}/templates/{template.pk}/apply/")
        self.assertContains(response, f'href="/templates/add/?next=/services/{self.service.pk}/"')


class TemplatePageTests(TemplateTestMixin, TestCase):
    def test_new_template_from_a_service_returns_to_it(self):
        next_url = self.service.get_absolute_url()
        response = self.client.get(f"/templates/add/?next={next_url}")
        self.assertContains(response, f'<input type="hidden" name="next" value="{next_url}">', html=True)
        response = self.client.post(
            "/templates/add/", {"name": "Benediction", "slot_names": "O salutaris\nTantum ergo", "next": next_url}
        )
        self.assertRedirects(response, next_url)
        self.assertEqual(SlotTemplate.objects.get(name="Benediction").slots, ["O salutaris", "Tantum ergo"])

    def test_a_next_address_off_this_site_is_ignored(self):
        for bad in ("javascript:alert(1)", "https://example.com/"):
            with self.subTest(next=bad):
                response = self.client.get("/templates/add/", {"next": bad})
                self.assertNotContains(response, bad)
                response = self.client.post("/templates/add/", {"name": f"T{len(bad)}", "slot_names": "A", "next": bad})
                self.assertRedirects(response, "/templates/")

    def test_the_ready_made_ones_can_be_edited(self):
        response = self.client.post(
            f"/templates/{self.mass.pk}/edit/", {"name": "Mass", "slot_names": "Introit\nOffertory motet"}
        )
        self.assertRedirects(response, "/templates/")
        self.mass.refresh_from_db()
        self.assertEqual(self.mass.slots, ["Introit", "Offertory motet"])

    def test_list_and_delete(self):
        response = self.client.get("/templates/")
        self.assertContains(response, "Alleluia or Tract")
        self.client.post(f"/templates/{self.mass.pk}/delete/")
        self.assertFalse(SlotTemplate.objects.filter(name="Mass").exists())

    def test_template_pages_are_for_conductors(self):
        self.client.force_login(User.objects.create_user(username="librarian", password="x"))
        for url in ("/templates/", "/templates/add/", f"/templates/{self.mass.pk}/edit/"):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)


class SlotTemplateFormTests(TestCase):
    def test_needs_a_slot(self):
        form = SlotTemplateForm(data={"name": "Empty", "slot_names": " \n  "})
        self.assertFalse(form.is_valid())
        self.assertIn("slot_names", form.errors)

    def test_a_slot_name_must_fit(self):
        form = SlotTemplateForm(data={"name": "Long", "slot_names": "x" * 51})
        self.assertFalse(form.is_valid())
        self.assertIn("up to 50 characters", form.errors["slot_names"][0])

    def test_slots_are_stored_tidily(self):
        form = SlotTemplateForm(data={"name": "Tidy", "slot_names": " Introit\n\nintroit\nKyrie "})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["slot_names"], "Introit\nKyrie")

    def test_names_are_unique(self):
        form = SlotTemplateForm(data={"name": "Mass", "slot_names": "Introit"})
        self.assertIn("name", form.errors)
