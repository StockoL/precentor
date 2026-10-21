from django import forms

from core.models import SiteConfig
from ordo.fields import OccasionChoiceField, OccasionMultipleChoiceField
from ordo.models import LiturgicalOccasion
from precentor_project.widgets import NativeDateInput

from .models import RolePiece, Service, ServiceRole, Term, TermMarker


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


class RolePieceForm(forms.ModelForm):
    class Meta:
        model = RolePiece
        fields = ["score"]  # noqa
