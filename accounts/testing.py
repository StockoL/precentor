"""
The one way tests make organisations and users, so the tests don't each
depend on how a user is built.

Everyone made here joins one shared "Test Church" unless a test passes
an organisation of its own, which is how the tests that keep
organisations apart will make two.
"""

from itertools import count

from .models import Organisation, Role, User

ROLES = tuple(Role.values)

_numbers = count(1)


def make_organisation(name="Test Church"):
    organisation, _ = Organisation.objects.get_or_create(name=name)
    return organisation


def make_user(role="conductor", *, organisation=None, email=None, password="testpass123"):
    if role not in ROLES:
        raise ValueError(f"Unknown role {role!r}; expected one of {ROLES}.")
    if email is None:
        email = f"{role}{next(_numbers)}@example.com"
    return User.objects.create_user(
        email=email,
        password=password,
        organisation=organisation or make_organisation(),
        role=role,
    )


def make_superuser(email="admin@example.com", password="testpass123"):
    """Someone who looks after the site from the admin pages: no
    organisation and no role."""
    return User.objects.create_superuser(email=email, password=password)
