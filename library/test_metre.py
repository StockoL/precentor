from django.test import SimpleTestCase

from .metre import normalise


class NormaliseTests(SimpleTestCase):
    def test_the_same_metre_written_three_ways_is_one(self):
        for written in ("88 88", "8.8.8.8", "LM", "lm", "8 8 8 8"):
            with self.subTest(written=written):
                self.assertEqual(normalise(written), "8.8.8.8")

    def test_the_short_names(self):
        self.assertEqual(normalise("CM"), "8.6.8.6")
        self.assertEqual(normalise("SM"), "6.6.8.6")

    def test_a_doubled_metre_keeps_its_d(self):
        for written in ("LMD", "LM D", "88 88 D", "8.8.8.8 D"):
            with self.subTest(written=written):
                self.assertEqual(normalise(written), "8.8.8.8 D")

    def test_lines_of_ten_or_more_stay_whole(self):
        self.assertEqual(normalise("10 10 10 10"), "10.10.10.10")
        self.assertEqual(normalise("87 87 77"), "8.7.8.7.7.7")
        self.assertEqual(normalise("11 10 11 10"), "11.10.11.10")

    def test_anything_else_is_kept_as_typed(self):
        self.assertEqual(normalise("  Irregular  "), "Irregular")
        self.assertEqual(normalise("87 87 with refrain"), "87 87 with refrain")
        self.assertEqual(normalise(""), "")
