from django import forms
from django.core.files.uploadedfile import UploadedFile

from .imaging import process_crest_image
from .models import SiteConfig


class SiteConfigForm(forms.ModelForm):
    class Meta:
        model = SiteConfig
        fields = [  # noqa
            "church_name",
            "crest_image",
            "house_accent_colour",
            "layout_style",
            "show_hymns_psalm",
        ]
        widgets = {  # noqa
            "house_accent_colour": forms.TextInput(attrs={"type": "color"}),
        }

    def clean_crest_image(self):
        image = self.cleaned_data.get("crest_image")
        # An untouched field comes back as the existing ImageFieldFile (not
        # an UploadedFile) — that, and a cleared field, must pass through
        # unprocessed rather than being fed to Pillow again.
        if not image or not isinstance(image, UploadedFile):
            return image
        return process_crest_image(image)
