from django import forms

from .imaging import process_crest_image, process_logo_image
from .models import SiteConfig

MAX_CREST_UPLOAD = 5 * 1024 * 1024  # 5 MB, far more than any crest needs
CONTENT_TYPES = {"png": "image/png", "jpg": "image/jpeg"}


class SiteConfigForm(forms.ModelForm):
    # The crest itself isn't a model field the form edits directly: an
    # upload is checked and processed to suit the chosen style, then stored
    # with SiteConfig.set_crest().
    crest_file = forms.FileField(
        label="Crest",
        required=False,
        widget=forms.FileInput(attrs={"accept": "image/png,image/jpeg,image/webp"}),
        help_text="A PNG, JPEG or WebP image, up to 5 MB.",
    )
    remove_crest = forms.BooleanField(label="Remove the crest", required=False)

    class Meta:
        model = SiteConfig
        fields = [  # noqa
            "church_name",
            "national_calendar",
            "crest_style",
            "house_accent_colour",
            "layout_style",
            "show_hymns_psalm",
        ]
        widgets = {  # noqa
            "crest_style": forms.RadioSelect,
            "house_accent_colour": forms.TextInput(attrs={"type": "color"}),
        }

    def clean_crest_file(self):
        upload = self.cleaned_data.get("crest_file")
        if upload and upload.size > MAX_CREST_UPLOAD:
            raise forms.ValidationError("Choose an image under 5 MB.")
        return upload

    def clean(self):
        cleaned = super().clean()
        upload = cleaned.get("crest_file")
        if upload and cleaned.get("remove_crest"):
            self.add_error("remove_crest", "Choose a new image or remove the crest, not both.")
        elif (
            "crest_style" in self.changed_data
            and self.instance.has_crest
            and not upload
            and not cleaned.get("remove_crest")
        ):
            # A logo kept at its own shape would look wrong as a banner, and
            # the other way round, so a new style needs its own image.
            self.add_error("crest_file", "Choose an image for the new style.")
        elif upload and "crest_file" not in self.errors:
            process = process_crest_image if cleaned.get("crest_style") == "banner" else process_logo_image
            try:
                cleaned["processed_crest"] = process(upload)
            except forms.ValidationError as error:
                self.add_error("crest_file", error)
        return cleaned

    def save(self, commit=True):
        config = super().save(commit=False)
        processed = self.cleaned_data.get("processed_crest")
        if self.cleaned_data.get("remove_crest"):
            config.clear_crest()
        elif processed:
            extension = processed.name.rsplit(".", 1)[-1]
            config.set_crest(processed.read(), CONTENT_TYPES[extension])
        if commit:
            config.save()
        return config
