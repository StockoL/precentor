from django.test import SimpleTestCase, TestCase

from .slot_kinds import KIND_CHOICES, NAMES, PROPER_PART_CHOICES, classify


class ClassifyTests(SimpleTestCase):
    def test_the_mass_template_classifies_itself(self):
        mass = ["Introit", "Kyrie", "Gloria", "Gradual", "Alleluia or Tract", "Credo",
                "Offertory", "Sanctus", "Agnus Dei", "Communion"]
        self.assertEqual([classify(name) for name in mass], [
            ("proper", "introit"), ("ordinary", ""), ("ordinary", ""), ("proper", "gradual"),
            ("proper", "alleluia_or_tract"), ("ordinary", ""), ("proper", "offertory"),
            ("ordinary", ""), ("ordinary", ""), ("proper", "communion"),
        ])

    def test_the_vespers_template_classifies_itself(self):
        vespers = ["Psalms", "Hymn", "Magnificat", "Marian antiphon"]
        self.assertEqual([classify(name) for name in vespers], [
            ("psalm", ""), ("hymn", ""), ("canticle", ""), ("antiphon", ""),
        ])

    def test_case_and_spacing_dont_matter(self):
        self.assertEqual(classify("  agnus   DEI "), ("ordinary", ""))

    def test_the_last_word_decides_otherwise(self):
        self.assertEqual(classify("Communion hymn"), ("hymn", ""))
        self.assertEqual(classify("Offertory motet"), ("motet", ""))
        self.assertEqual(classify("Opening voluntary"), ("organ", ""))
        self.assertEqual(classify("Responsorial psalm"), ("psalm", ""))

    def test_a_magnificat_antiphon_knows_its_proper_part(self):
        self.assertEqual(classify("Magnificat antiphon"), ("antiphon", "magnificat_antiphon"))

    def test_a_sequence_is_a_proper_and_a_responsory_a_kind(self):
        self.assertEqual(classify("Sequence"), ("proper", "sequence"))
        self.assertEqual(classify("Palm Sunday responsory"), ("responsory", ""))
        self.assertEqual(classify("Responsories"), ("responsory", ""))

    def test_a_name_it_doesnt_know_is_other(self):
        self.assertEqual(classify("Procession"), ("other", ""))
        self.assertEqual(classify(""), ("other", ""))

    def test_the_table_only_uses_known_kinds_and_parts(self):
        kinds = {value for value, _ in KIND_CHOICES}
        parts = {value for value, _ in PROPER_PART_CHOICES} | {""}
        for name, (kind, part) in NAMES.items():
            with self.subTest(name=name):
                self.assertIn(kind, kinds)
                self.assertIn(part, parts)


class SlotKindOnSaveTests(TestCase):
    def setUp(self):
        from datetime import date

        from precentor_project.testing import make_term

        from .models import Service

        self.service = Service.objects.create(term=make_term(), date=date(2026, 1, 11), service_type="Sung Mass")

    def add(self, name, **fields):
        from .models import ServiceRole

        return ServiceRole.objects.create(service=self.service, role_name=name, **fields)

    def test_a_new_slot_is_classified_from_its_name(self):
        slot = self.add("Introit")
        self.assertEqual((slot.kind, slot.proper_part), ("proper", "introit"))
        self.assertEqual(slot.get_kind_display(), "Proper")

    def test_a_kind_chosen_by_hand_is_kept(self):
        slot = self.add("Introit", kind="hymn")
        self.assertEqual(slot.kind, "hymn")
        slot.save()
        slot.refresh_from_db()
        self.assertEqual(slot.kind, "hymn")

    def test_a_template_makes_classified_slots(self):
        from precentor_project.testing import make_slot_template

        template = make_slot_template(organisation=self.service.organisation, slot_names="Kyrie\nCommunion hymn")
        template.apply_to(self.service)
        self.assertEqual(list(self.service.roles.values_list("kind", flat=True)), ["ordinary", "hymn"])


class ClassifyExistingSlotsTests(TestCase):
    def test_slots_from_before_kinds_are_classified_and_others_left(self):
        import importlib
        from datetime import date

        from django.apps import apps

        from precentor_project.testing import make_term

        from .models import Service, ServiceRole

        migration = importlib.import_module("planning.migrations.0020_classify_existing_slots")
        service = Service.objects.create(term=make_term(), date=date(2026, 1, 11), service_type="Sung Mass")
        for name in ["Introit", "Communion hymn", "Procession"]:
            ServiceRole.objects.create(service=service, role_name=name)
        chosen = ServiceRole.objects.create(service=service, role_name="Gradual", kind="psalm")
        # update() skips save(), so these are as slots were before the migration.
        ServiceRole.objects.exclude(pk=chosen.pk).update(kind="", proper_part="")

        migration.classify_existing(apps, None)
        self.assertEqual(list(service.roles.values_list("role_name", "kind", "proper_part")), [
            ("Introit", "proper", "introit"),
            ("Communion hymn", "hymn", ""),
            ("Procession", "other", ""),
            ("Gradual", "psalm", ""),
        ])


class KindBadgeTests(TestCase):
    def test_each_slot_shows_its_kind(self):
        from datetime import date

        from accounts.testing import make_user
        from precentor_project.testing import make_term

        from .models import Service, ServiceRole

        viewer = make_user("viewer")
        term = make_term(organisation=viewer.organisation)
        service = Service.objects.create(term=term, date=date(2026, 1, 11), service_type="Sung Mass")
        introit = ServiceRole.objects.create(service=service, role_name="Introit")
        hymn = ServiceRole.objects.create(service=service, role_name="Recessional hymn")
        self.client.force_login(viewer)
        response = self.client.get(service.get_absolute_url())
        badge = '<span id="kind-badge-{}" class="badge badge--kind">{}</span>'
        self.assertContains(response, badge.format(introit.pk, "Proper"), html=True)
        self.assertContains(response, badge.format(hymn.pk, "Hymn"), html=True)


class AddSlotKindTests(TestCase):
    def setUp(self):
        from datetime import date

        from accounts.testing import make_user
        from precentor_project.testing import make_term

        from .models import Service

        conductor = make_user("conductor")
        self.client.force_login(conductor)
        term = make_term(organisation=conductor.organisation)
        self.service = Service.objects.create(term=term, date=date(2026, 1, 11), service_type="Sung Mass")

    def add(self, **data):
        self.client.post(f"/services/{self.service.pk}/roles/add/", data)
        return self.service.roles.get()

    def test_left_blank_the_kind_comes_from_the_name(self):
        slot = self.add(role_name="Introit", kind="")
        self.assertEqual((slot.kind, slot.proper_part), ("proper", "introit"))

    def test_a_chosen_kind_is_kept(self):
        self.assertEqual(self.add(role_name="Introit", kind="hymn").kind, "hymn")

    def test_the_form_offers_the_kinds_with_the_name_first(self):
        response = self.client.get(self.service.get_absolute_url())
        self.assertContains(response, '<option value="" selected>From the slot&#x27;s name</option>', html=True)
        self.assertContains(response, '<option value="antiphon">Antiphon</option>', html=True)


class ChangeKindTests(TestCase):
    def setUp(self):
        from datetime import date

        from accounts.testing import make_user
        from precentor_project.testing import make_term

        from .models import Service, ServiceRole

        self.conductor = make_user("conductor")
        self.client.force_login(self.conductor)
        term = make_term(organisation=self.conductor.organisation)
        self.service = Service.objects.create(term=term, date=date(2026, 1, 11), service_type="Sung Mass")
        self.slot = ServiceRole.objects.create(service=self.service, role_name="Introit")
        self.url = f"/roles/{self.slot.pk}/kind/"

    def test_without_javascript_it_changes_and_says_so(self):
        response = self.client.post(self.url, {"kind": "hymn"}, follow=True)
        self.slot.refresh_from_db()
        self.assertEqual((self.slot.kind, self.slot.proper_part), ("hymn", "introit"))
        self.assertContains(response, "The Introit is now shown as Hymn.")

    def test_with_javascript_only_the_badge_comes_back(self):
        response = self.client.post(self.url, {"kind": "motet"}, headers={"X-Requested-With": "XMLHttpRequest"})
        self.assertEqual(list(response.json()["fragments"]), [f"kind-badge-{self.slot.pk}"])
        self.assertIn(">Motet<", response.json()["fragments"][f"kind-badge-{self.slot.pk}"])

    def test_a_kind_that_isnt_listed_is_refused(self):
        response = self.client.post(self.url, {"kind": "fanfare"}, headers={"X-Requested-With": "XMLHttpRequest"})
        self.assertEqual(response.status_code, 400)
        self.slot.refresh_from_db()
        self.assertEqual(self.slot.kind, "proper")

    def test_only_a_conductor_can_change_it(self):
        from accounts.testing import make_user

        self.client.force_login(make_user("librarian", organisation=self.conductor.organisation))
        self.assertEqual(self.client.post(self.url, {"kind": "hymn"}).status_code, 403)

    def test_each_slot_has_the_select_with_its_kind_chosen(self):
        response = self.client.get(self.service.get_absolute_url())
        self.assertContains(response, f'<select id="kind-{self.slot.pk}" name="kind">')
        self.assertContains(response, '<option value="proper" selected>Proper</option>', html=True)


class SequenceAndResponsoryMigrationTests(TestCase):
    """Migration 0028 reclassifies slots made as Other before these kinds
    existed, and leaves a kind someone chose."""

    def test_slots_still_other_are_reclassified(self):
        import importlib
        from datetime import date

        from django.apps import apps

        from precentor_project.testing import make_slot_template, make_term

        from .models import Service, ServiceRole

        term = make_term()
        service = Service.objects.create(term=term, date=date(2026, 1, 4), service_type="Sung Mass")
        sequence = ServiceRole.objects.create(service=service, role_name="Sequence", kind="other")
        responsory = ServiceRole.objects.create(service=service, role_name="Palm responsory", kind="other")
        chosen = ServiceRole.objects.create(service=service, role_name="Sequence motet", kind="motet")
        template = make_slot_template(organisation=term.organisation, slot_names="Sequence")
        template.template_slots.update(kind="other", proper_part="")
        importlib.import_module("planning.migrations.0028_sequence_and_responsory").reclassify(apps, None)
        for slot, expected in [(sequence, ("proper", "sequence")), (responsory, ("responsory", "")),
                               (chosen, ("motet", ""))]:
            slot.refresh_from_db()
            self.assertEqual((slot.kind, slot.proper_part), expected)
        self.assertEqual(template.template_slots.get().proper_part, "sequence")
