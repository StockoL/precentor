from django import forms

from core.models import SiteConfig
from ordo.fields import OccasionMultipleChoiceField
from ordo.models import LiturgicalOccasion, UseType
from precentor_project.widgets import NativeDateInput

from .models import Hymn, Hymnal, HymnEntry, Score, Tune


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
            "text",
            "translation",
            "translation_credit",
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
        # Only the church's own use types to tick, and only those accepted.
        self.fields["suited_use_types"].queryset = UseType.objects.for_organisation(self.instance.organisation_id)
        # The church's own calendar, in both forms, and whatever this score
        # is already tagged with.
        keep = list(self.instance.suited_occasions.values_list("pk", flat=True)) if self.instance.pk else []
        self.fields["suited_occasions"].queryset = LiturgicalOccasion.objects.listable(
            SiteConfig.national_calendar_of(self.instance.organisation_id), keep
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


class ScoreImportForm(forms.Form):
    """The spreadsheet to import, saved as CSV."""

    file = forms.FileField(
        label="Your CSV file",
        widget=forms.ClearableFileInput(attrs={"accept": ".csv,text/csv"}),
    )


class HymnalForm(forms.ModelForm):
    class Meta:
        model = Hymnal
        fields = ["name", "short_name", "copies_owned", "filing_location", "archived"]  # noqa

    def clean_short_name(self):
        """
        One book per code in each church, as "NEH 123" has to mean one
        book. The database refuses a second too, but only this check can
        say so plainly, as the church is set by the view, not typed. It
        ignores case, so "neh" can't sit beside "NEH".
        """
        code = self.cleaned_data["short_name"].strip()
        same = Hymnal.objects.filter(organisation_id=self.instance.organisation_id, short_name__iexact=code)
        if same.exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(f"You already have a hymnal with the code {code}.")
        return code


class HymnForm(forms.ModelForm):
    """A hymn's optional details. Its tags work as a score's do, from the
    church's own use types and calendar, but use types are only picked
    here: new ones are made on the score form."""

    class Meta:
        model = Hymn
        fields = [  # noqa
            "first_line", "metre", "text", "text_credit", "suited_use_types", "suited_seasons", "suited_occasions",
        ]
        field_classes = {"suited_occasions": OccasionMultipleChoiceField}  # noqa

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["suited_use_types"].queryset = UseType.objects.for_organisation(self.instance.organisation_id)
        keep = list(self.instance.suited_occasions.values_list("pk", flat=True)) if self.instance.pk else []
        self.fields["suited_occasions"].queryset = LiturgicalOccasion.objects.listable(
            SiteConfig.national_calendar_of(self.instance.organisation_id), keep
        )


class TuneForm(forms.ModelForm):
    class Meta:
        model = Tune
        fields = ["name", "metre"]  # noqa

    def clean_name(self):
        """One tune per name in each church, whatever its case, so two
        Reptons can't split a tune's history in two."""
        name = " ".join(self.cleaned_data["name"].split())
        same = Tune.objects.filter(organisation_id=self.instance.organisation_id, name__iexact=name)
        if same.exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(f"You already have a tune called {name}.")
        return name


class HymnEntryForm(forms.ModelForm):
    """A hymn's tune in one book: chosen from the church's own tunes."""

    class Meta:
        model = HymnEntry
        fields = ["tune"]  # noqa

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tune"].queryset = Tune.objects.for_organisation(self.instance.organisation_id)
