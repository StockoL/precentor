from django.test import SimpleTestCase

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
