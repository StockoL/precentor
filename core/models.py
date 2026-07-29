from django.db import models

LAYOUT_STYLE_CHOICES = [
    ("columns", "Newspaper columns"),
    ("simple", "Simple single column"),
]


class SiteConfig(models.Model):
    church_name = models.CharField(max_length=200, blank=True)
    crest_image = models.ImageField(upload_to="site_config/", blank=True)
    house_accent_colour = models.CharField(max_length=7, default="#8b1a2b")
    layout_style = models.CharField(
        max_length=20, choices=LAYOUT_STYLE_CHOICES, default="columns"
    )
    show_hymns_psalm = models.BooleanField(default=True)

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
