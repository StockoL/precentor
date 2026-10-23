from django import forms
from django.contrib.auth.forms import AuthenticationForm, BaseUserCreationForm
from django.db import transaction

from .models import Organisation, Role, User
from .organisations import create_organisation


class EmailAuthenticationForm(AuthenticationForm):
    """
    Django's login form, asking for an email address. The field keeps the
    name "username" because that's what the login view and authenticate()
    expect; the user model's USERNAME_FIELD makes it the email.
    """

    username = forms.EmailField(
        label="Email address",
        widget=forms.EmailInput(attrs={"autofocus": True, "autocomplete": "email"}),
    )


class SignUpForm(BaseUserCreationForm):
    """
    A new church and the person signing it up, who becomes its owner and a
    Conductor. Django's base form checks the two passwords match, runs the
    site's password rules and stores the password hashed.
    """

    church_name = forms.CharField(
        label="Your church's name",
        max_length=Organisation._meta.get_field("name").max_length,
        widget=forms.TextInput(attrs={"autofocus": True, "autocomplete": "organization"}),
        help_text="Or your school or music department. You can change it later.",
    )

    class Meta:
        model = User
        fields = ["name", "email"]  # noqa
        labels = {"name": "Your name", "email": "Email address"}  # noqa
        widgets = {  # noqa
            "name": forms.TextInput(attrs={"autocomplete": "name"}),
            "email": forms.EmailInput(attrs={"autocomplete": "email"}),
        }

    field_order = ["church_name", "name", "email", "password1", "password2"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].required = True
        # Django lists its password rules as bullet points; one plain line
        # says the same. The rules themselves are still checked in full.
        self.fields["password1"].help_text = (
            "At least 8 characters, not all numbers, not a common password "
            "and not too like your name or email."
        )
        self.fields["password2"].label = "Password again"
        self.fields["password2"].help_text = ""
        # The church's name comes first, so the cursor starts there.
        self.fields["email"].widget.attrs.pop("autofocus", None)

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Someone already has an account with this email address. Try signing in.")
        return email

    @transaction.atomic
    def save(self):
        """The church and its first person together, or neither, so there's
        no saving one without the other."""
        user = super().save(commit=False)
        user.organisation = create_organisation(self.cleaned_data["church_name"])
        user.role = Role.CONDUCTOR
        user.is_owner = True
        user.save()
        return user
