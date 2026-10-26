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
        ServiceRole.objects.create(service=service, role_name="Introit")
        ServiceRole.objects.create(service=service, role_name="Recessional hymn")
        self.client.force_login(viewer)
        response = self.client.get(service.get_absolute_url())
        self.assertContains(response, '<span class="badge badge--kind">Proper</span>', html=True)
        self.assertContains(response, '<span class="badge badge--kind">Hymn</span>', html=True)
