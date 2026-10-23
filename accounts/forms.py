from django import forms
from django.contrib.auth.forms import AuthenticationForm, BaseUserCreationForm
from django.db import transaction

from .models import Invitation, Organisation, Role, User
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


class NewPersonForm(BaseUserCreationForm):
    """
    What anyone joining Precentor gives: their name, email and a password.
    Django's base form checks the two passwords match, runs the site's
    password rules and stores the password hashed. Signing up a church and
    accepting an invitation both build on this, so the rules are the same.
    """

    class Meta:
        model = User
        fields = ["name", "email"]  # noqa
        labels = {"name": "Your name", "email": "Email address"}  # noqa
        widgets = {  # noqa
            "name": forms.TextInput(attrs={"autocomplete": "name"}),
            "email": forms.EmailInput(attrs={"autocomplete": "email"}),
        }

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
        # The cursor starts in the first field, not Django's choice of email.
        self.fields["email"].widget.attrs.pop("autofocus", None)
        next(iter(self.fields.values())).widget.attrs["autofocus"] = True

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Someone already has an account with this email address. Try signing in.")
        return email


class SignUpForm(NewPersonForm):
    """A new church and the person signing it up, who becomes its owner
    and a Conductor."""

    church_name = forms.CharField(
        label="Your church's name",
        max_length=Organisation._meta.get_field("name").max_length,
        widget=forms.TextInput(attrs={"autocomplete": "organization"}),
        help_text="Or your school or music department. You can change it later.",
    )

    field_order = ["church_name", "name", "email", "password1", "password2"]

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


class JoinForm(NewPersonForm):
    """Someone accepting an invitation, who joins its church in its role."""

    def __init__(self, *args, invitation, **kwargs):
        super().__init__(*args, **kwargs)
        self.invitation = invitation

    @transaction.atomic
    def save(self):
        """The person, and the invitation marked used by them. If someone
        else used it first, Invitation.Gone undoes the new account too."""
        user = super().save(commit=False)
        user.organisation = self.invitation.organisation
        user.role = self.invitation.role
        user.save()
        if not self.invitation.use(user):
            raise Invitation.Gone
        return user


class InvitationForm(forms.ModelForm):
    """The owner choosing who to invite and as what."""

    # What each role may do, beside its name, so the choice is clear.
    ROLE_LABELS = {
        Role.CONDUCTOR: "Conductor: plans terms, services and music",
        Role.LIBRARIAN: "Librarian: looks after the library",
        Role.VIEWER: "Viewer: sees everything and can comment",
    }

    class Meta:
        model = Invitation
        fields = ["role", "note"]  # noqa
        widgets = {"role": forms.RadioSelect}  # noqa

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"].choices = list(self.ROLE_LABELS.items())
        self.fields["role"].initial = Role.VIEWER
