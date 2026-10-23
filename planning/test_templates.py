from datetime import date

from django.test import TestCase

from accounts.testing import make_organisation, make_user
from precentor_project.testing import make_score, make_slot_template, make_term

from .forms import SlotTemplateForm
from .models import Service, ServiceRole, SlotTemplate

MASS = ["Introit", "Kyrie", "Gloria", "Gradual", "Alleluia or Tract", "Credo", "Offertory", "Sanctus", "Agnus Dei", "Communion"]
VESPERS = ["Psalms", "Hymn", "Magnificat", "Marian antiphon"]


class TemplateTestMixin:
    def setUp(self):
        self.conductor = make_user("conductor")
        self.client.force_login(self.conductor)
        term = make_term(name="T", start_date=date(2026, 1, 1), end_date=date(2026, 3, 31), calendar_use="current")
        self.service = Service.objects.create(term=term, date=date(2026, 1, 11), service_type="Sung Mass")
        # The church's own Mass and Vespers, with the ready-made slots.
        self.mass = make_slot_template(name="Mass", slot_names="\n".join(MASS))
        self.vespers = make_slot_template(name="Vespers", slot_names="\n".join(VESPERS))

    def slot_names(self):
        return list(self.service.roles.values_list("role_name", flat=True))


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
        self.client.force_login(make_user("librarian"))
        self.assertEqual(self.client.post(url).status_code, 403)
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
        self.client.force_login(make_user("librarian"))
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

    def test_a_church_has_one_template_per_name_whatever_the_case(self):
        church = make_organisation("St Cecilia's")
        make_slot_template(name="Mass", slot_names="Introit", organisation=church)
        form = SlotTemplateForm(data={"name": "mass", "slot_names": "Introit"}, instance=SlotTemplate(organisation=church))
        self.assertEqual(form.errors["name"], ["You already have a template called mass."])

    def test_another_church_can_use_the_same_name(self):
        make_slot_template(name="Mass", slot_names="Introit", organisation=make_organisation("St Elsewhere"))
        form = SlotTemplateForm(
            data={"name": "Mass", "slot_names": "Introit"},
            instance=SlotTemplate(organisation=make_organisation("St Cecilia's")),
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_editing_a_template_keeps_its_own_name(self):
        church = make_organisation("St Cecilia's")
        mass = make_slot_template(name="Mass", slot_names="Introit", organisation=church)
        form = SlotTemplateForm(data={"name": "Mass", "slot_names": "Introit\nKyrie"}, instance=mass)
        self.assertTrue(form.is_valid(), form.errors)


class OneTemplatePerServiceTests(TemplateTestMixin, TestCase):
    def setUp(self):
        super().setUp()

    def apply(self, template, **data):
        return self.client.post(f"/services/{self.service.pk}/templates/{template.pk}/apply/", data, follow=True)

    def test_the_first_template_needs_no_asking_and_is_remembered(self):
        self.apply(self.mass)
        self.service.refresh_from_db()
        self.assertEqual(self.service.slot_template, self.mass)
        self.assertEqual(self.slot_names(), MASS)

    def test_another_template_asks_before_replacing(self):
        self.apply(self.mass)
        response = self.apply(self.vespers)
        self.assertTemplateUsed(response, "planning/apply_template_confirm.html")
        self.assertContains(response, "Replace the Mass slots with Vespers?")
        self.assertEqual(self.slot_names(), MASS)

    def test_replacing_keeps_slots_with_pieces(self):
        from planning.models import RolePiece

        self.apply(self.mass)
        introit = self.service.roles.get(role_name="Introit")
        RolePiece.objects.create(service_role=introit, score=make_score(title="Rorate", composer_surname="Plainchant"))
        response = self.apply(self.vespers, replace="1")
        self.assertEqual(self.slot_names(), ["Introit", "Psalms", "Hymn", "Magnificat", "Marian antiphon"])
        self.assertContains(response, "Now using Vespers: 4 slots added. Kept Introit, which has pieces proposed.")
        self.service.refresh_from_db()
        self.assertEqual(self.service.slot_template, self.vespers)

    def test_slots_added_by_hand_also_ask_first(self):
        ServiceRole.objects.create(service=self.service, role_name="Offertory motet")
        response = self.apply(self.mass)
        self.assertContains(response, "Replace the current slots with Mass?")

    def test_the_same_template_again_just_fills_in(self):
        self.apply(self.mass)
        self.service.roles.get(role_name="Credo").delete()
        response = self.apply(self.mass)
        self.assertContains(response, "Added 1 slot from Mass.")

    def test_buttons_that_would_replace_carry_the_dialogs_wording(self):
        self.apply(self.mass)
        response = self.client.get(self.service.get_absolute_url())
        self.assertContains(response, 'data-confirm-title="Replace the Mass slots with Vespers?"')
        self.assertContains(response, 'data-confirm-label="Use Vespers"')
        self.assertNotContains(response, 'data-confirm-label="Use Mass"')
        self.assertContains(response, 'aria-current="true">Mass</button>')
