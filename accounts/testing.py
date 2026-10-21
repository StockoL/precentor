"""
The one way tests make users. Every test module goes through make_user,
so when the custom user model replaces Django's default one, only this
file changes, not every test that needs someone signed in.

For now a role is a Group: Conductor and Librarian each have one, made
by accounts/migrations/0001_create_groups.py, and a Viewer is a user in
neither.
"""

from itertools import count

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

ROLES = ("conductor", "librarian", "viewer")

_numbers = count(1)


def make_user(role="conductor", *, email=None, password="testpass123"):
    if role not in ROLES:
        raise ValueError(f"Unknown role {role!r}; expected one of {ROLES}.")
    if email is None:
        email = f"{role}{next(_numbers)}@example.com"
    # The username is the email for now, so tests that sign in by
    # filling the login form already use the address they'll use later.
    user = get_user_model().objects.create_user(username=email, email=email, password=password)
    if role != "viewer":
        user.groups.add(Group.objects.get_or_create(name=role.title())[0])
    return user
