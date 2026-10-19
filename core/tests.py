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
