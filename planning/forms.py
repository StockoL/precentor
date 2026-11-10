from django import forms
from django.utils.formats import date_format

from core.models import SiteConfig
from library.models import Hymnal, HymnEntry
from ordo.fields import OccasionChoiceField, OccasionMultipleChoiceField
from ordo.models import LiturgicalOccasion, UseType
from precentor_project.widgets import NativeDateInput

from .models import (
    ONE_PIECE_MESSAGE, RolePiece, Service, ServiceRole, SlotTemplate, TemplateSlot, Term, TermMarker,
)
from .slot_kinds import KIND_CHOICES, PROPER_PART_CHOICES
from .suggestions import facts_for, grouped, slot_use_type


class TermForm(forms.ModelForm):
    class Meta:
        model = Term
        fields = ["name", "start_date", "end_date", "calendar_use"]  # noqa
        widgets = {  # noqa
            "start_date": NativeDateInput(),
            "end_date": NativeDateInput(),
        }

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start_date"), cleaned.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", "A term can't end before it starts.")
        elif start and end:
            self.refuse_stranding(start, end)
        return cleaned

    def refuse_stranding(self, start, end):
        """
        New dates mustn't leave any of the term's services outside it. Only
        checked when a date has changed, so a term whose services are
        already outside it, from before this check, can still be renamed.
        The error goes beside the date that changed, or above both.
        """
        changed = [name for name in ("start_date", "end_date") if name in self.changed_data]
        if not self.instance.pk or not changed:
            return
        outside = self.instance.services.exclude(date__range=(start, end)).order_by("date")
        count = outside.count()
        if not count:
            return
        first = date_format(outside.first().date)
        if count == 1:
            message = f"A service on {first} would fall outside these dates. Move or delete it first."
        else:
            message = (f"{count} services would fall outside these dates, the first on {first}. "
                       "Move or delete them first.")
        self.add_error(changed[0] if len(changed) == 1 else None, message)


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

    def clean(self):
        """A service falls within its term, both ends included. The term is
        the one the service already belongs to, never one from the form."""
        cleaned = super().clean()
        day, term = cleaned.get("date"), self.instance.term
        if day and not term.start_date <= day <= term.end_date:
            self.add_error("date", f"{term} runs from {date_format(term.start_date)} to {date_format(term.end_date)}, "
                                   "so the service needs a date in between.")
        return cleaned


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
    """A template's name. Its slots are the formset beside it."""

    class Meta:
        model = SlotTemplate
        fields = ["name"]  # noqa

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


class TemplateSlotForm(forms.ModelForm):
    """One slot of a template: its name, and its kind and proper part,
    which are worked out from the name when left blank."""

    class Meta:
        model = TemplateSlot
        fields = ["name", "kind", "proper_part"]  # noqa
        help_texts = {"kind": ""}  # noqa

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["kind"].choices = [("", "From the slot's name")] + KIND_CHOICES
        self.fields["proper_part"].choices = [("", "Not a proper")] + PROPER_PART_CHOICES

    def clean_name(self):
        return " ".join(self.cleaned_data["name"].split())


class BaseTemplateSlotFormSet(forms.BaseInlineFormSet):
    """A template's slots, as rows, with Django's own order and delete
    fields and a few blank rows for new ones. Works without JavaScript."""

    def add_fields(self, form, index):
        super().add_fields(form, index)
        form.fields["DELETE"].label = "Remove"

    def kept_forms(self):
        """The rows to keep, in the order asked for: filled in and not
        ticked for removal."""
        return [form for form in self.ordered_forms if form.cleaned_data.get("name")]

    def clean(self):
        """At least one slot, and each name once whatever its case, as a
        service can't hold two slots of one name."""
        super().clean()
        if any(form.errors for form in self.forms):
            return
        names = [form.cleaned_data["name"].lower() for form in self.kept_forms()]
        if not names:
            raise forms.ValidationError("Add at least one slot.")
        repeated = next((name for name in names if names.count(name) > 1), None)
        if repeated:
            raise forms.ValidationError(f"{repeated.capitalize()} is in the template twice.")

    def save_slots(self):
        """Save the kept rows in their new order, numbered from 1, and
        remove those ticked for removal."""
        for form in self.deleted_forms:
            if form.instance.pk:
                form.instance.delete()
        for position, form in enumerate(self.kept_forms(), start=1):
            slot = form.save(commit=False)
            slot.template = self.instance
            slot.position = position
            slot.save()


TemplateSlotFormSet = forms.inlineformset_factory(
    SlotTemplate, TemplateSlot, form=TemplateSlotForm, formset=BaseTemplateSlotFormSet,
    extra=3, can_delete=True, can_order=True,
)


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
        self.fields["reference"].help_text = 'Anything not in the library can be typed here, e.g. "Psalm 150, tone 4"'
        if role.hymnals_on_offer:
            self.fields["hymnal"].queryset = Hymnal.objects.filter(pk__in=[h.pk for h in role.hymnals_on_offer])
            self.fields["hymnal"].initial = role.default_hymnal
            self.order_fields(["hymnal", "number", "reference", "score"])
            self.fields["reference"].label = "Or type a reference"
            # Typed as text, a hymn number couldn't be counted as that hymn.
            self.fields["reference"].help_text = 'For anything not in a hymnal or the library, e.g. "Psalm 150, tone 4"'
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
        if self.already_proposed(cleaned, number):
            raise forms.ValidationError("That's already proposed for this slot.")
        return cleaned

    def already_proposed(self, cleaned, number):
        """
        Whether the slot already has this piece: the same score, the same
        number in the same book, or the same reference whatever its
        capitals. Checked here only, not by the database, as slots on the
        live site may already hold repeats from before.
        """
        pieces = self.role.pieces.all()
        if cleaned.get("score"):
            return pieces.filter(score=cleaned["score"]).exists()
        if number:
            return pieces.filter(hymn_entry__hymnal=cleaned.get("hymnal"), hymn_entry__number__iexact=number).exists()
        return pieces.filter(reference__iexact=cleaned["reference"]).exists()

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
