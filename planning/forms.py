from django import forms

from .models import RolePiece, Service, ServiceRole, Term


class TermForm(forms.ModelForm):
    class Meta:
        model = Term
        fields = ["name", "start_date", "end_date", "tradition", "calendar_use"]  # noqa
        widgets = {  # noqa
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = [  # noqa
            "date",
            "service_type",
            "occasion",
            "additional_occasions",
            "tradition",
            "calendar_use",
        ]
        widgets = {  # noqa
            "date": forms.DateInput(attrs={"type": "date"}),
        }


class ServiceRoleForm(forms.ModelForm):
    class Meta:
        model = ServiceRole
        fields = ["role_name", "is_not_applicable"]  # noqa
        widgets = {  # noqa
            "role_name": forms.TextInput(
                attrs={"placeholder": "e.g. Setting, Anthem, Canticles, Responses…"}
            ),
        }


class RolePieceForm(forms.ModelForm):
    class Meta:
        model = RolePiece
        fields = ["score"]  # noqa
