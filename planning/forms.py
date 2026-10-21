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
        choices = LiturgicalOccasion.objects.listable(SiteConfig.get_solo().national_calendar, keep)
        self.fields["occasion"].queryset = choices
        self.fields["additional_occasions"].queryset = choices


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
    class Meta:
        model = RolePiece
        fields = ["score"]  # noqa
