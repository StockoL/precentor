from django import forms

from core.models import SiteConfig
from ordo.fields import OccasionChoiceField, OccasionMultipleChoiceField
from ordo.models import LiturgicalOccasion
from precentor_project.widgets import NativeDateInput

from .models import RolePiece, Service, ServiceRole, SlotTemplate, Term, TermMarker


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
            "hymns",
            "psalm",
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
    class Meta:
        model = ServiceRole
        fields = ["role_name", "is_not_applicable"]  # noqa
        widgets = {  # noqa
            "role_name": forms.TextInput(
                attrs={
                    "placeholder": "e.g. Mass setting, Introit, Offertory motet, "
                    "Communion hymn, Magnificat…"
                }
            ),
        }


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
        names = SlotTemplate(slot_names=text).slots
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


class RolePieceForm(forms.ModelForm):
    """
    Proposing a score for a slot. The scores on offer, and the only ones
    accepted, are the service's own church's, ranked for it: the list is
    set before the form checks anything, so another church's score can't
    be proposed even by a hand-made request.
    """

    class Meta:
        model = RolePiece
        fields = ["score"]  # noqa

    def __init__(self, *args, service, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["score"].queryset = service.suggested_scores()
