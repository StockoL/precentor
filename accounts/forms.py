from django import forms
from django.contrib.auth.forms import AuthenticationForm


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
