from django import forms

from core.models import SiteConfig
from library.models import Hymnal, HymnEntry
from ordo.fields import OccasionChoiceField, OccasionMultipleChoiceField
from ordo.models import LiturgicalOccasion, UseType
from precentor_project.widgets import NativeDateInput

from .models import ONE_PIECE_MESSAGE, RolePiece, Service, ServiceRole, SlotTemplate, Term, TermMarker
from .slot_kinds import KIND_CHOICES
from .suggestions import facts_for, grouped, slot_use_type


class TermForm(forms.ModelForm):
    class Meta:
        model = Term
        fields = ["name", "start_date", "end_date", "calendar_use"]  # noqa
        widgets = {  # noqa
            "start_date": NativeDateInput(),
            "end_date": NativeDateInput(),
        }


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = [  # noqa
            "date",
            "service_type",
            "occasion",
            "additional_occasions",
            "calendar_use",
        ]
        widgets = {  # noqa
            "date": NativeDateInput(),
        }
        field_classes = {  # noqa
            "occasion": OccasionChoiceField,
            "additional_occasions": OccasionMultipleChoiceField,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only the church's own calendar, in both forms, and whatever this
        # service already has.
        keep = []
        if self.instance.pk:
            keep = [self.instance.occasion_id, *self.instance.additional_occasions.values_list("pk", flat=True)]
        # A new service has no organisation until it's saved, so ask its term's.
        church = self.instance.term.organisation_id if self.instance.term_id else None
        choices = LiturgicalOccasion.objects.listable(SiteConfig.national_calendar_of(church), keep)
        self.fields["occasion"].queryset = choices
        self.fields["additional_occasions"].queryset = choices
        # Say what blank means: the term's calendar, by name.
        term = getattr(self.instance, "term", None)
        if term:
            field = self.fields["calendar_use"]
            field.choices = [("", f"As the term: {term.get_calendar_use_display()}"), *field.choices[1:]]


class TermMarkerForm(forms.ModelForm):
    class Meta:
        model = TermMarker
        fields = ["date", "text"]  # noqa
        widgets = {  # noqa
            "date": NativeDateInput(),
        }


class ServiceRoleForm(forms.ModelForm):
    """Adding a slot. Its kind can be chosen, or left for the slot's name
    to decide when it's saved, which suits most slots."""

    class Meta:
        model = ServiceRole
        fields = ["role_name", "kind", "is_not_applicable"]  # noqa
        widgets = {  # noqa
            "role_name": forms.TextInput(
                attrs={
                    "placeholder": "e.g. Mass setting, Introit, Offertory motet, "
                    "Communion hymn, Magnificat…"
                }
            ),
        }
        help_texts = {"kind": ""}  # noqa

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["kind"].choices = [("", "From the slot's name")] + KIND_CHOICES


class SlotTemplateForm(forms.ModelForm):
    class Meta:
        model = SlotTemplate
        fields = ["name", "slot_names"]  # noqa
        widgets = {  # noqa
            "slot_names": forms.Textarea(attrs={"rows": 12}),
        }

    def clean_name(self):
        """
        One template per name in each church. The database refuses a second
        too, but only this check can say so plainly: Django leaves out a
        rule on fields the form doesn't show, and organisation is set by
        the view, not typed. It ignores case, as "mass" would be confusing
        beside "Mass".
        """
        name = self.cleaned_data["name"]
        same_name = SlotTemplate.objects.filter(organisation_id=self.instance.organisation_id, name__iexact=name)
        if same_name.exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(f"You already have a template called {name}.")
        return name

    def clean_slot_names(self):
        text = self.cleaned_data["slot_names"]
        names = SlotTemplate.names_from_text(text)
        if not names:
            raise forms.ValidationError("Add at least one slot.")
        limit = ServiceRole._meta.get_field("role_name").max_length
        too_long = [name for name in names if len(name) > limit]
        if too_long:
            raise forms.ValidationError(
                f"A slot's name can be up to {limit} characters: {too_long[0][:30]}… is longer."
            )
        # Stored tidily: one name a line, as the template will use them.
        return "\n".join(names)

    def save(self, commit=True):
        """Until the form shows the slots as rows, its text becomes them."""
        template = super().save(commit=commit)
        template.set_slots(template.names_from_text(template.slot_names))
        return template


class RolePieceForm(forms.ModelForm):
    """
    Proposing a piece for a slot: a score from the library, a hymn by its
    book and number, or a typed reference, one of the three. The scores
    and hymnals on offer, and the only ones accepted, are the service's
    own church's: the lists are set before the form checks anything, so
    another church's can't be chosen even by a hand-made request. Hymn
    slots ask for a book and number first when the church has hymnals;
    psalm and antiphon slots ask for the reference first.
    """

    hymnal = forms.ModelChoiceField(queryset=Hymnal.objects.none(), required=False, empty_label=None)
    number = forms.CharField(max_length=10, required=False)

    class Meta:
        model = RolePiece
        fields = ["score", "reference"]  # noqa

    def __init__(self, *args, role, **kwargs):
        super().__init__(*args, **kwargs)
        self.role = role
        self.fields["score"].queryset = role.service.suggested_scores()
        if role.takes_reference_first:
            self.order_fields(["reference", "score"])
            self.fields["reference"].label = "Reference"
            self.fields["score"].label = "Or a score from the library"
        else:
            self.fields["score"].label = "Score"
            self.fields["reference"].label = "Or type a reference"
        if role.hymnals_on_offer:
            self.fields["hymnal"].queryset = Hymnal.objects.filter(pk__in=[h.pk for h in role.hymnals_on_offer])
            self.fields["hymnal"].initial = role.default_hymnal
            self.order_fields(["hymnal", "number", "reference", "score"])
            self.fields["reference"].label = "Or type a reference"
            # Typed as text, a hymn number couldn't be counted as that hymn.
            self.fields["reference"].help_text = 'For anything not in a hymnal, e.g. "Psalm 150, tone 4"'
        else:
            del self.fields["hymnal"], self.fields["number"]

    def clean(self):
        """
        Exactly one of a score, a hymn number or a reference. The database
        has the same rule, but Django leaves a rule out of a form's checks
        when it names a field the form doesn't show, and hymn_entry is set
        from a book and number rather than shown, so the form says it
        itself. A hymnal is always chosen on a Hymn slot, so only a number
        means a hymn was given.
        """
        cleaned = super().clean()
        number = cleaned.get("number", "").strip()
        if number and not cleaned.get("hymnal"):
            self.add_error("hymnal", "Choose the hymnal it's in.")
        given = [bool(cleaned.get("score")), bool(number), bool(cleaned.get("reference"))]
        if given.count(True) != 1:
            raise forms.ValidationError(ONE_PIECE_MESSAGE)
        return cleaned

    def save(self, commit=True):
        """A hymn's entry is found, or made with its hymn the first time
        that number is used, only once everything else is known to be
        right."""
        number = self.cleaned_data.get("number", "").strip()
        if number:
            self.instance.hymn_entry = HymnEntry.find_or_make(self.cleaned_data["hymnal"], number)
        return super().save(commit)

    def show_suggestions(self):
        """For the propose page: the score list in the suggestion groups,
        each option with its reasons. Only what's shown changes; the
        scores accepted are still the queryset above."""
        service = self.role.service
        use_types = UseType.objects.for_organisation(service.organisation_id)
        window = SiteConfig.of(service.organisation).repeat_window_weeks
        groups = grouped(facts_for(service, window), slot_use_type(self.role, use_types))
        self.fields["score"].choices = [("", "---------")] + [
            (label, [(score.pk, f"{score}: {'; '.join(reasons)}" if reasons else str(score))
                     for score, reasons in entries])
            for label, entries in groups
        ]
