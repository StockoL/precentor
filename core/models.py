from django.core.validators import RegexValidator
from django.db import models

from ordo.models import NATIONAL_CALENDAR_CHOICES

# The colour is written into an inline style on the music list, so it
# must be exactly a hex colour: autoescaping stops HTML, not extra CSS.
validate_hex_colour = RegexValidator(
    r"^#[0-9a-fA-F]{6}$",
    "Enter a colour as # and six hex digits, for example #8b1a2b.",
)

LAYOUT_STYLE_CHOICES = [
    ("columns", "Newspaper columns"),
    ("simple", "Simple single column"),
]


class SiteConfig(models.Model):
    church_name = models.CharField(
        max_length=200, blank=True, help_text="Shown at the top of the music list."
    )
    crest_image = models.ImageField(
        "crest",
        upload_to="site_config/",
        blank=True,
        help_text="Shown at the top of the music list, cropped to a banner shape.",
    )
    house_accent_colour = models.CharField(
        "accent colour",
        max_length=7,
        default="#8b1a2b",
        validators=[validate_hex_colour],
        help_text="Used for services without an occasion colour.",
    )
    national_calendar = models.CharField(
        "calendar",
        max_length=20,
        choices=NATIONAL_CALENDAR_CHOICES,
        default="general_roman",
        help_text="Adds your country's own days, and its changes of date and rank, "
        "to the general calendar when occasions are suggested.",
    )
    layout_style = models.CharField(
        "music list layout",
        max_length=20,
        choices=LAYOUT_STYLE_CHOICES,
        default="columns",
    )
    show_hymns_psalm = models.BooleanField(
        "show hymns and psalm on the music list", default=True
    )

    def save(self, *args, **kwargs):
        # Enforce singleton regardless of how this is constructed.
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass  # the singleton row is never deleted

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return self.church_name or "Site configuration"
