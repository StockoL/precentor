import hashlib

from django.core.validators import RegexValidator
from django.db import models
from django.urls import reverse

from ordo.models import NATIONAL_CALENDAR_CHOICES

# The colour is written into an inline style on the music list, so it
# must be exactly a hex colour: autoescaping stops HTML, not extra CSS.
validate_hex_colour = RegexValidator(
    r"^#[0-9a-fA-F]{6}$",
    "Enter a colour as # and six hex digits, for example #8b1a2b.",
)

CREST_STYLE_CHOICES = [
    ("logo", "Logo beside the church's name"),
    ("banner", "Banner across the top"),
]

LAYOUT_STYLE_CHOICES = [
    ("columns", "Newspaper columns"),
    ("simple", "Simple single column"),
]


class SiteConfig(models.Model):
    # Each organisation has its own settings, made by SiteConfig.of().
    organisation = models.OneToOneField(
        "accounts.Organisation", on_delete=models.CASCADE, related_name="settings"
    )
    church_name = models.CharField(
        max_length=200, blank=True, help_text="Shown at the top of the music list."
    )
    # The crest itself, kept in the database because a host's disk is wiped
    # on every deploy. Set and cleared through set_crest() and clear_crest().
    crest = models.BinaryField(blank=True, default=b"", editable=False)
    crest_type = models.CharField(max_length=20, blank=True, editable=False)  # e.g. "image/png"
    crest_version = models.CharField(max_length=12, blank=True, editable=False)
    crest_style = models.CharField(
        "crest style", max_length=10, choices=CREST_STYLE_CHOICES, default="logo"
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

    def set_crest(self, data, content_type):
        """Store a processed crest. The version is a fingerprint of the
        image, so its address changes whenever the image does and
        browsers can cache it for good."""
        self.crest = data
        self.crest_type = content_type
        self.crest_version = hashlib.sha256(data).hexdigest()[:12]

    def clear_crest(self):
        self.crest, self.crest_type, self.crest_version = b"", "", ""

    @property
    def has_crest(self):
        return bool(self.crest_version)

    @property
    def crest_layout(self):
        """How the music list shows the crest: "banner", "logo", or "" with
        no crest at all."""
        return self.crest_style if self.has_crest else ""

    @property
    def crest_url(self):
        """Where the crest is served: the church's, at its current version."""
        return reverse("core:crest", args=[self.organisation_id, self.crest_version]) if self.has_crest else ""

    @classmethod
    def of(cls, organisation):
        """An organisation's settings, made with the defaults the first time
        they're needed, so a new church needs no setting up."""
        config, _ = cls.objects.get_or_create(organisation=organisation)
        return config

    @classmethod
    def national_calendar_of(cls, organisation_id):
        """The church's national calendar, for the occasion menus: the
        general one when the church isn't known or has no settings yet.
        It only reads, so building a form never creates a settings row."""
        default = cls._meta.get_field("national_calendar").default
        if organisation_id is None:
            return default
        chosen = cls.objects.filter(organisation_id=organisation_id).values_list("national_calendar", flat=True)
        return chosen.first() or default

    def __str__(self):
        return self.church_name or "Site configuration"
