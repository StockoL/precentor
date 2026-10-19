from django import forms

from .models import RolePiece, Service, ServiceRole, Term, TermMarker


class NativeDateInput(forms.DateInput):
    """
    The browser's own date picker. <input type="date"> only accepts an
    ISO value (YYYY-MM-DD), but Django renders a date in the locale's
    first input format, which for en-gb is DD/MM/YYYY and would leave
    every edit form's date blank. Pinning the format fixes that for any
    locale.
    """

    input_type = "date"

    def __init__(self, attrs=None):
        super().__init__(attrs=attrs, format="%Y-%m-%d")


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
