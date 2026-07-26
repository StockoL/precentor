from django import forms

from .models import RolePiece, Service, ServiceRole, Term


class TermForm(forms.ModelForm):
    class Meta:
        model = Term
        fields = ["name", "start_date", "end_date"]  # noqa
        widgets = {  # noqa
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ["date", "service_type", "occasion"]  # noqa
        widgets = {  # noqa
            "date": forms.DateInput(attrs={"type": "date"}),
        }


class ServiceRoleForm(forms.ModelForm):
    class Meta:
        model = ServiceRole
        fields = ["role_name", "is_not_applicable"]  # noqa


class RolePieceForm(forms.ModelForm):
    class Meta:
        model = RolePiece
        fields = ["score"]  # noqa
