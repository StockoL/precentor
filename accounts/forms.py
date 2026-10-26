from django import forms
from django.contrib.auth.forms import AuthenticationForm, BaseUserCreationForm, PasswordChangeForm, SetPasswordForm
from django.db import transaction

from .models import Invitation, Organisation, Role, User
from .organisations import create_organisation
from .throttling import clear_attempts, limit_reached, record_attempt


def plain_password_fields(form, first, second, label="Password"):
    """
    Django lists its password rules as bullet points under the first box
    and labels the second "confirmation"; one plain line and "again" say
    the same. The rules themselves are still checked in full.
    """
    form.fields[first].label = label
    form.fields[first].help_text = (
        "At least 8 characters, not all numbers, not a common password "
        "and not too like your name or email."
    )
    form.fields[second].label = f"{label} again"
    form.fields[second].help_text = ""


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

    # After this many wrong passwords for one address, signing in to it is
    # refused for a while, so a password can't be guessed by trying.
    FAILED_LIMIT = 5
    LOCKED_FOR = 15 * 60  # seconds after the last wrong password

    error_messages = {
        **AuthenticationForm.error_messages,
        "throttled": (
            "Too many wrong passwords for this address. Wait 15 minutes and try again, "
            "or ask whoever runs Precentor for your church for a reset link."
        ),
    }

    def clean(self):
        email = (self.cleaned_data.get("username") or "").lower()
        if email and limit_reached("sign-in", email, self.FAILED_LIMIT):
            # Refused before the password is even checked, so guessing
            # gains nothing while it lasts.
            raise forms.ValidationError(self.error_messages["throttled"], code="throttled")
        try:
            cleaned = super().clean()
        except forms.ValidationError:
            if email:
                record_attempt("sign-in", email, self.LOCKED_FOR)
            raise
        clear_attempts("sign-in", email)
        return cleaned


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
        plain_password_fields(self, "password1", "password2")
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


class RoleForm(forms.ModelForm):
    """The owner changing someone's role from the members page."""

    class Meta:
        model = User
        fields = ["role"]  # noqa

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.is_owner:
            # The owner can't be a Viewer. The database refuses it too, but
            # Django leaves out a rule on a field the form doesn't show
            # (is_owner), so the form offers only what's allowed and says
            # plainly why if anything else is sent.
            field = self.fields["role"]
            field.choices = [choice for choice in field.choices if choice[0] != Role.VIEWER]
            field.error_messages["invalid_choice"] = (
                "The owner must be a Conductor or a Librarian. Hand ownership to someone else first."
            )


class NewPasswordForm(SetPasswordForm):
    """Choosing a new password from a reset link."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        plain_password_fields(self, "new_password1", "new_password2", label="New password")


class ChangePasswordForm(PasswordChangeForm):
    """Changing your own password, with the same plain help as sign-up."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["old_password"].label = "Current password"
        plain_password_fields(self, "new_password1", "new_password2", label="New password")


class DeleteAccountForm(forms.Form):
    """Asks for the person's password before their account is deleted, so
    nobody at a computer left signed in can do it for them."""

    password = forms.CharField(
        label="Your password", widget=forms.PasswordInput(attrs={"autocomplete": "current-password"})
    )

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_password(self):
        password = self.cleaned_data["password"]
        if not self.user.check_password(password):
            raise forms.ValidationError("That isn't your password.")
        return password


class DeleteChurchForm(forms.Form):
    """The owner types the church's name to confirm, as one click is too
    easy for something that can't be undone. Capitals and spaces at the
    ends don't matter: it's a check of intent, not of typing."""

    name = forms.CharField(label="Type the church's name to confirm")

    def __init__(self, *args, organisation, **kwargs):
        super().__init__(*args, **kwargs)
        self.organisation = organisation

    def clean_name(self):
        name = self.cleaned_data["name"]
        if name.strip().casefold() != self.organisation.name.strip().casefold():
            raise forms.ValidationError("That isn't the church's name.")
        return name

