from django.test import TestCase

from .forms import SiteConfigForm


class SiteConfigFormLabelTests(TestCase):
    def test_settings_form_labels_read_naturally(self):
        form = str(SiteConfigForm())
        for label in ("Crest:", "Accent colour:", "Music list layout:",
                      "Show hymns and psalm on the music list:"):
            with self.subTest(label=label):
                self.assertIn(f"{label}</label>", form)
        for old in ("House accent colour", "Crest image", "Show hymns psalm"):
            with self.subTest(old=old):
                self.assertNotIn(old, form)


class AccentColourTests(TestCase):
    def form(self, colour):
        return SiteConfigForm(data={
            "house_accent_colour": colour,
            "layout_style": "columns",
        })

    def test_six_digit_hex_is_accepted(self):
        for colour in ("#8b1a2b", "#8B1A2B", "#000000"):
            with self.subTest(colour=colour):
                self.assertTrue(self.form(colour).is_valid())

    def test_anything_else_is_refused(self):
        # The last two would add CSS to the inline style on the music list.
        for colour in ("red", "#fff", "8b1a2b", "#8b1a2", "#8b1a2;", "red;x"):
            with self.subTest(colour=colour):
                form = self.form(colour)
                self.assertFalse(form.is_valid())
                self.assertIn("house_accent_colour", form.errors)
