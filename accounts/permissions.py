"""
Who may do what. Each check takes a user and returns True or False, and
views and templates ask these instead of looking at roles themselves,
so the rules live in one place.

Nobody passes a check by being signed out, deactivated or a superuser.
A superuser looks after the site from the admin pages and has no role
inside the app.

For now a role is a Group (see accounts/testing.py); when the custom
user model arrives, only _has_role changes.
"""


def _has_role(user, *roles):
    if not (user.is_authenticated and user.is_active):
        return False
    return user.groups.filter(name__in=[role.title() for role in roles]).exists()


def can_plan(user):
    """Terms, services, slots and pieces: proposing, confirming, marking N/A."""
    return _has_role(user, "conductor")


def can_edit_library(user):
    """Scores and their physical details: adding, editing, deleting."""
    return _has_role(user, "conductor", "librarian")
