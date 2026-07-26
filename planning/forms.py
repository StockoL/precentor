from django import forms

from .models import RolePiece, ServiceRole


class ServiceRoleForm(forms.ModelForm):
    class Meta:
        model = ServiceRole
        fields = ["role_name", "is_not_applicable"]  # noqa


class RolePieceForm(forms.ModelForm):
    class Meta:
        model = RolePiece
        fields = ["score"]  # noqa
