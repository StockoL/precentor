from datetime import date

from django.test import TestCase

from accounts.testing import make_organisation, make_user
from precentor_project.testing import make_score, make_slot_template, make_term, template_form_data

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
        names = SlotTemplate.names_from_text("  Introit \n\nKyrie\nkyrie\n  Offertory   motet  ")
        self.assertEqual(names, ["Introit", "Kyrie", "Offertory motet"])


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
        data = template_form_data("Benediction", ["O salutaris", "Tantum ergo"])
        response = self.client.post("/templates/add/", {**data, "next": next_url})
        self.assertRedirects(response, next_url)
        self.assertEqual(SlotTemplate.objects.get(name="Benediction").slots, ["O salutaris", "Tantum ergo"])

    def test_a_next_address_off_this_site_is_ignored(self):
        for bad in ("javascript:alert(1)", "https://example.com/"):
            with self.subTest(next=bad):
                response = self.client.get("/templates/add/", {"next": bad})
                self.assertNotContains(response, bad)
                data = template_form_data(f"T{len(bad)}", ["A"])
                response = self.client.post("/templates/add/", {**data, "next": bad})
                self.assertRedirects(response, "/templates/")

    def test_the_ready_made_ones_can_be_edited(self):
        keep = ["Introit"]
        data = template_form_data(
            "Mass", ["Offertory motet"], template=self.mass, remove=[n for n in MASS if n not in keep],
        )
        response = self.client.post(f"/templates/{self.mass.pk}/edit/", data)
        self.assertRedirects(response, "/templates/")
        self.assertEqual(self.mass.slots, ["Introit", "Offertory motet"])

    def test_slots_can_be_reordered_and_keep_a_chosen_kind(self):
        data = template_form_data("Vespers", template=self.vespers, order=list(reversed(VESPERS)))
        data["slots-1-kind"] = "motet"  # Hymn, sung as a motet here
        self.assertRedirects(self.client.post(f"/templates/{self.vespers.pk}/edit/", data), "/templates/")
        self.assertEqual(self.vespers.slots, list(reversed(VESPERS)))
        self.assertEqual(self.vespers.template_slots.get(name="Hymn").kind, "motet")

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
    def formset(self, *names):
        from .forms import TemplateSlotFormSet

        data = template_form_data("T", names)
        return TemplateSlotFormSet(data, instance=SlotTemplate(), prefix="slots")

    def test_needs_a_slot(self):
        formset = self.formset()
        self.assertFalse(formset.is_valid())
        self.assertEqual(formset.non_form_errors(), ["Add at least one slot."])

    def test_a_slot_name_must_fit(self):
        formset = self.formset("x" * 51)
        self.assertFalse(formset.is_valid())
        self.assertIn("at most 50 characters", str(formset.errors))

    def test_each_name_once_and_tidied(self):
        formset = self.formset(" Introit ", "introit")
        self.assertFalse(formset.is_valid())
        self.assertEqual(formset.non_form_errors(), ["Introit is in the template twice."])
        formset = self.formset("  Offertory   motet ")
        self.assertTrue(formset.is_valid())
        self.assertEqual(formset.forms[0].cleaned_data["name"], "Offertory motet")

    def test_a_church_has_one_template_per_name_whatever_the_case(self):
        church = make_organisation("St Cecilia's")
        make_slot_template(name="Mass", slot_names="Introit", organisation=church)
        form = SlotTemplateForm(data={"name": "mass"}, instance=SlotTemplate(organisation=church))
        self.assertEqual(form.errors["name"], ["You already have a template called mass."])

    def test_another_church_can_use_the_same_name(self):
        make_slot_template(name="Mass", slot_names="Introit", organisation=make_organisation("St Elsewhere"))
        church = make_organisation("St Cecilia's")
        form = SlotTemplateForm(data={"name": "Mass"}, instance=SlotTemplate(organisation=church))
        self.assertTrue(form.is_valid(), form.errors)

    def test_editing_a_template_keeps_its_own_name(self):
        church = make_organisation("St Cecilia's")
        mass = make_slot_template(name="Mass", slot_names="Introit", organisation=church)
        form = SlotTemplateForm(data={"name": "Mass"}, instance=mass)
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


class TemplateSlotTests(TemplateTestMixin, TestCase):
    def test_a_templates_slots_are_classified_and_applied_with_their_kinds(self):
        self.assertEqual(
            list(self.mass.template_slots.values_list("name", "kind", "proper_part"))[:2],
            [("Introit", "proper", "introit"), ("Kyrie", "ordinary", "")],
        )
        slot = self.mass.template_slots.get(name="Introit")
        slot.kind = "hymn"
        slot.save()
        self.mass.apply_to(self.service)
        self.assertEqual(self.service.roles.get(role_name="Introit").kind, "hymn")

    def test_existing_templates_are_split_into_rows(self):
        import importlib

        from django.apps import apps

        from .models import TemplateSlot

        migration = importlib.import_module("planning.migrations.0027_split_template_slots")
        TemplateSlot.objects.all().delete()
        self.vespers.slot_names = "Psalms\n\nhymn\nHymn\nMagnificat"
        self.vespers.save()
        migration.split_into_rows(apps, None)
        self.assertEqual(
            list(self.vespers.template_slots.values_list("name", "kind", "position")),
            [("Psalms", "psalm", 1), ("hymn", "hymn", 2), ("Magnificat", "canticle", 3)],
        )
        self.assertEqual(self.vespers.template_slots.first().organisation, self.vespers.organisation)
