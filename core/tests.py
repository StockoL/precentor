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
            "house_accent_colour": colour, "crest_style": "logo",
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

    def logo(self, upload):
        from PIL import Image

        from .imaging import process_logo_image

        return Image.open(process_logo_image(upload))

    def test_a_logo_keeps_its_own_shape_and_is_fitted_inside_600(self):
        for size, expected in (((1200, 900), (600, 450)), ((300, 1200), (150, 600)), ((400, 400), (400, 400))):
            with self.subTest(size=size):
                self.assertEqual(self.logo(self.upload(size)).size, expected)

    def test_a_logo_keeps_its_transparency(self):
        self.assertEqual(self.logo(self.upload((500, 500), mode="RGBA")).mode, "RGBA")

    def test_a_tiny_logo_is_refused(self):
        from django.core.exceptions import ValidationError

        from .imaging import process_logo_image

        with self.assertRaisesMessage(ValidationError, "at least 150px on its shorter side"):
            process_logo_image(self.upload((400, 120)))



class SettingsAccessTests(TestCase):
    url = "/settings/"

    def test_visitor_is_sent_to_log_in(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, f"/accounts/login/?next={self.url}")

    def test_librarian_is_refused(self):
        self.client.force_login(make_user("librarian"))
        self.assertEqual(self.client.get(self.url).status_code, 403)
        response = self.client.post(self.url, {
            "church_name": "Changed", "house_accent_colour": "#000000", "crest_style": "logo",
            "layout_style": "columns", "national_calendar": "general_roman",
        })
        self.assertEqual(response.status_code, 403)
        self.assertEqual(SiteConfig.get_solo().church_name, "")

    def test_conductor_can_change_the_settings(self):
        self.client.force_login(make_user("conductor"))
        self.assertEqual(self.client.get(self.url).status_code, 200)
        response = self.client.post(self.url, {
            "church_name": "St Mary's", "house_accent_colour": "#123456", "crest_style": "logo",
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


class CrestStorageTests(TestCase):
    def test_a_crest_is_kept_in_the_database_with_its_type(self):
        config = SiteConfig.get_solo()
        config.set_crest(b"png bytes", "image/png")
        config.save()
        config = SiteConfig.get_solo()
        self.assertEqual(bytes(config.crest), b"png bytes")
        self.assertEqual(config.crest_type, "image/png")
        self.assertTrue(config.has_crest)

    def test_the_version_changes_only_when_the_image_does(self):
        config = SiteConfig.get_solo()
        config.set_crest(b"first", "image/png")
        first = config.crest_version
        config.set_crest(b"first", "image/png")
        self.assertEqual(config.crest_version, first)
        config.set_crest(b"second", "image/png")
        self.assertNotEqual(config.crest_version, first)

    def test_clearing_leaves_no_crest(self):
        config = SiteConfig.get_solo()
        config.set_crest(b"png bytes", "image/png")
        config.clear_crest()
        self.assertFalse(config.has_crest)
        self.assertEqual((bytes(config.crest), config.crest_type), (b"", ""))

    def test_a_new_site_starts_with_the_logo_style(self):
        self.assertEqual(SiteConfig.get_solo().crest_style, "logo")


class CrestViewTests(TestCase):
    def setUp(self):
        config = SiteConfig.get_solo()
        config.set_crest(b"png bytes", "image/png")
        config.save()
        self.config = config

    def test_anyone_can_fetch_the_crest_and_keep_it(self):
        response = self.client.get(self.config.crest_url)
        self.assertEqual(response.content, b"png bytes")
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertEqual(response["Cache-Control"], "public, max-age=31536000, immutable")
        self.assertEqual(self.client.post(self.config.crest_url).status_code, 405)

    def test_an_old_address_or_no_crest_finds_nothing(self):
        self.assertEqual(self.client.get("/settings/crest/000000000000/").status_code, 404)
        self.config.clear_crest()
        self.config.save()
        self.assertEqual(self.config.crest_url, "")
        self.assertEqual(self.client.get("/settings/crest/anything/").status_code, 404)


class CrestFormTests(TestCase):
    def upload(self, size, name="crest.png"):
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

        buffer = BytesIO()
        Image.new("RGB", size, "navy").save(buffer, "PNG")
        return SimpleUploadedFile(name, buffer.getvalue())

    def save(self, style, upload=None, **extra):
        data = {"house_accent_colour": "#8b1a2b", "crest_style": style, "layout_style": "columns",
                "national_calendar": "general_roman", **extra}
        form = SiteConfigForm(data=data, files={"crest_file": upload} if upload else {},
                              instance=SiteConfig.get_solo())
        if form.is_valid():
            form.save()
        return form

    def crest_size(self):
        from io import BytesIO

        from PIL import Image

        return Image.open(BytesIO(bytes(SiteConfig.get_solo().crest))).size

    def test_each_style_is_processed_to_suit_it_and_stored(self):
        self.assertTrue(self.save("banner", self.upload((1000, 1000))).is_valid())
        self.assertEqual(self.crest_size(), (1600, 400))
        self.assertEqual(SiteConfig.get_solo().crest_type, "image/jpeg")
        self.assertTrue(self.save("logo", self.upload((1200, 900))).is_valid())
        self.assertEqual(self.crest_size(), (600, 450))

    def test_a_new_style_asks_for_a_new_image(self):
        self.save("logo", self.upload((400, 400)))
        form = self.save("banner")
        self.assertEqual(form.errors["crest_file"], ["Choose an image for the new style."])
        self.assertEqual(SiteConfig.get_solo().crest_style, "logo")

    def test_remove_clears_the_crest_and_cannot_come_with_a_new_one(self):
        self.save("logo", self.upload((400, 400)))
        self.assertIn("remove_crest", self.save("logo", self.upload((400, 400)), remove_crest="on").errors)
        self.assertTrue(self.save("logo", remove_crest="on").is_valid())
        self.assertFalse(SiteConfig.get_solo().has_crest)

    def test_an_upload_over_5_mb_or_too_small_is_refused(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        big = SimpleUploadedFile("crest.png", b"x" * (5 * 1024 * 1024 + 1))
        self.assertEqual(self.save("logo", big).errors["crest_file"], ["Choose an image under 5 MB."])
        self.assertIn("at least 150px", self.save("logo", self.upload((400, 100))).errors["crest_file"][0])
        self.assertFalse(SiteConfig.get_solo().has_crest)
