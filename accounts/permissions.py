"""
Who may do what. Each check takes a user and returns True or False, and
views and templates ask these instead of looking at roles themselves,
so the rules live in one place.

Nobody passes a check by being signed out, deactivated or a superuser.
A superuser looks after the site from the admin pages and has no role
inside the app.

For now a role is a Group (see accounts/testing.py); when the custom
user model arrives, only _role changes.
"""


def _role(user):
    """The person's one role, or None if they have none. A user in neither
    group is a Viewer, unless they're a superuser, who has no role."""
    if not (user.is_authenticated and user.is_active):
        return None
    groups = set(user.groups.values_list("name", flat=True))
    for role in ("conductor", "librarian"):
        if role.title() in groups:
            return role
    return None if user.is_superuser else "viewer"


def _has_role(user, *roles):
    return _role(user) in roles


def can_plan(user):
    """Terms, services, slots and pieces: proposing, confirming, marking N/A."""
    return _has_role(user, "conductor")


def can_edit_library(user):
    """Scores and their physical details: adding, editing, deleting."""
    return _has_role(user, "conductor", "librarian")


def can_comment(user):
    """Comments and replies, and closing or reopening a thread."""
    return _has_role(user, "conductor", "librarian", "viewer")


def can_manage_settings(user):
    """The church's name, crest, colours and calendar."""
    return _has_role(user, "conductor")
