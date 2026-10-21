from django.test import TestCase

from accounts.testing import make_user

from .forms import SiteConfigForm
from .models import SiteConfig


class SiteConfigSingletonTests(TestCase):
    def test_get_solo_creates_the_row_with_defaults(self):
        config = SiteConfig.get_solo()
        self.assertEqual(config.pk, 1)
        self.assertEqual(config.house_accent_colour, "#8b1a2b")
        self.assertEqual(SiteConfig.objects.count(), 1)

    def test_saving_a_new_object_overwrites_the_one_row(self):
        SiteConfig(church_name="St Mary's").save()
        SiteConfig(church_name="St Anne's").save()
        self.assertEqual(SiteConfig.objects.count(), 1)
        self.assertEqual(SiteConfig.get_solo().church_name, "St Anne's")

    def test_delete_leaves_the_row_in_place(self):
        config = SiteConfig.get_solo()
        config.delete()
        self.assertTrue(SiteConfig.objects.filter(pk=1).exists())


class SiteConfigFormLabelTests(TestCase):
    def test_settings_form_labels_read_naturally(self):
        form = str(SiteConfigForm())
        for label in ("Calendar:", "Crest:", "Accent colour:", "Music list layout:",
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
            "layout_style": "columns", "national_calendar": "general_roman",
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


class CrestProcessingTests(TestCase):
    def upload(self, size, mode="RGB", fmt="PNG"):
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

        buffer = BytesIO()
        Image.new(mode, size, "navy").save(buffer, fmt)
        return SimpleUploadedFile(f"crest.{fmt.lower()}", buffer.getvalue())

    def processed(self, upload):
        from PIL import Image

        from .imaging import process_crest_image

        result = process_crest_image(upload)
        return result, Image.open(result)

    def test_already_cropped_image_is_kept_at_the_banner_size(self):
        result, image = self.processed(self.upload((1600, 400)))
        self.assertEqual(image.size, (1600, 400))
        self.assertEqual(result.name, "crest.jpg")

    def test_raw_upload_is_centre_cropped_to_the_banner_shape(self):
        # What a visitor without JavaScript sends: any shape at all.
        for size in ((1000, 1000), (3000, 400)):
            with self.subTest(size=size):
                _, image = self.processed(self.upload(size))
                self.assertEqual(image.size, (1600, 400))

    def test_transparency_is_kept_as_png(self):
        result, image = self.processed(self.upload((1600, 400), mode="RGBA"))
        self.assertEqual(result.name, "crest.png")
        self.assertEqual(image.mode, "RGBA")

    def test_bad_uploads_are_refused(self):
        from django.core.exceptions import ValidationError
        from django.core.files.uploadedfile import SimpleUploadedFile

        from .imaging import process_crest_image

        cases = {
            "not an image": SimpleUploadedFile("crest.png", b"not an image"),
            "too small": self.upload((400, 100)),
            "wrong format": self.upload((1600, 400), fmt="GIF"),
        }
        for case, upload in cases.items():
            with self.subTest(case=case), self.assertRaises(ValidationError):
                process_crest_image(upload)

    def test_form_runs_uploads_through_the_processing(self):
        form = SiteConfigForm(
            data={"house_accent_colour": "#8b1a2b", "layout_style": "columns", "national_calendar": "general_roman"},
            files={"crest_image": self.upload((1000, 1000))},
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["crest_image"].name, "crest.jpg")


class SettingsAccessTests(TestCase):
    url = "/settings/"

    def test_visitor_is_sent_to_log_in(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, f"/accounts/login/?next={self.url}")

    def test_librarian_is_refused(self):
        self.client.force_login(make_user("librarian"))
        self.assertEqual(self.client.get(self.url).status_code, 403)
        response = self.client.post(self.url, {
            "church_name": "Changed", "house_accent_colour": "#000000",
            "layout_style": "columns", "national_calendar": "general_roman",
        })
        self.assertEqual(response.status_code, 403)
        self.assertEqual(SiteConfig.get_solo().church_name, "")

    def test_conductor_can_change_the_settings(self):
        self.client.force_login(make_user("conductor"))
        self.assertEqual(self.client.get(self.url).status_code, 200)
        response = self.client.post(self.url, {
            "church_name": "St Mary's", "house_accent_colour": "#123456",
            "layout_style": "simple", "national_calendar": "england",
        })
        self.assertRedirects(response, self.url)
        config = SiteConfig.get_solo()
        self.assertEqual(config.church_name, "St Mary's")
        self.assertEqual(config.house_accent_colour, "#123456")
        self.assertEqual(config.national_calendar, "england")
        self.assertFalse(config.show_hymns_psalm)


class NationalCalendarSettingTests(TestCase):
    def test_defaults_to_the_general_calendar(self):
        self.assertEqual(SiteConfig.get_solo().national_calendar, "general_roman")

    def test_settings_page_offers_each_calendar_with_its_help_text(self):
        self.client.force_login(make_user("conductor"))
        response = self.client.get("/settings/")
        for label in ("General Roman Calendar", "England", "Wales"):
            with self.subTest(label=label):
                self.assertContains(response, f">{label}</option>")
        # as_field_group links the help text to the select.
        self.assertContains(response, 'aria-describedby="id_national_calendar_helptext"')
        self.assertContains(response, "Adds your country's own days")
