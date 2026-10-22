from django import forms

from core.models import SiteConfig
from ordo.fields import OccasionMultipleChoiceField
from ordo.models import LiturgicalOccasion, UseType
from precentor_project.widgets import NativeDateInput

from .models import Score


class ScoreForm(forms.ModelForm):
    # Use types are plain labels, so new ones can be typed in and are
    # created on save. Seasons and occasions are pick-only: an occasion
    # carries a date rule, so a made-up one would have no date.
    new_use_types = forms.CharField(
        label="Other uses",
        required=False,
        help_text="Not in the list? Type new ones, separated by commas.",
    )

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
            "range_soprano",
            "range_alto",
            "range_tenor",
            "range_bass",
        ]
        widgets = {  # noqa
            "last_sung_manual": NativeDateInput(),
            # Suggests the voicings already in the library (a <datalist> in
            # score_form.html), so SATB and S.A.T.B. don't split in two.
            "voicing": forms.TextInput(attrs={"list": "voicing-options"}),
        }
        field_classes = {"suited_occasions": OccasionMultipleChoiceField}  # noqa

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # The church's own calendar, in both forms, and whatever this score
        # is already tagged with.
        keep = list(self.instance.suited_occasions.values_list("pk", flat=True)) if self.instance.pk else []
        self.fields["suited_occasions"].queryset = LiturgicalOccasion.objects.listable(
            SiteConfig.get_solo().national_calendar, keep
        )

    def clean_new_use_types(self):
        """The typed names, trimmed, blanks dropped, each once whatever
        its case."""
        names = []
        for name in self.cleaned_data["new_use_types"].split(","):
            name = " ".join(name.split())
            if name and name.lower() not in (n.lower() for n in names):
                names.append(name)
        return names

    def add_new_use_types(self, score):
        """Tag the score with each typed use type, reusing one of the
        church's own whose name matches in any case ("mass" finds "Mass").
        Another church's use types are never reused or seen."""
        church_use_types = UseType.objects.filter(organisation=score.organisation)
        for name in self.cleaned_data.get("new_use_types", []):
            use_type = church_use_types.filter(name__iexact=name).first()
            if use_type is None:
                use_type = UseType.objects.create(name=name, organisation=score.organisation)
            score.suited_use_types.add(use_type)

    def save(self, commit=True):
        score = super().save(commit=commit)
        if commit:
            self.add_new_use_types(score)
        else:
            # With commit=False, Django saves many-to-many links later in
            # save_m2m(), so the new use types are added then too.
            save_m2m = self.save_m2m

            def save_m2m_and_new_use_types():
                save_m2m()
                self.add_new_use_types(score)

            self.save_m2m = save_m2m_and_new_use_types
        return score
