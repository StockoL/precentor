from django import forms

from precentor_project.widgets import NativeDateInput

from .models import Score


class ScoreForm(forms.ModelForm):
    class Meta:
        model = Score
        fields = [  # noqa
            "title",
            "composer_surname",
            "composer_other_names",
            "arranger",
            "editor",
            "voicing",
            "soprano_parts",
            "alto_parts",
            "tenor_parts",
            "bass_parts",
            "language",
            "copies_owned",
            "filing_location",
            "suited_use_types",
            "suited_seasons",
            "suited_occasions",
            "duration_minutes",
            "last_sung_manual",
            "background",
            "notes",
        ]
        widgets = {  # noqa
            "last_sung_manual": NativeDateInput(),
        }
