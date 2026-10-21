"""
Who may do what. Each check takes a user and returns True or False, and
views and templates ask these instead of looking at roles themselves,
so the rules live in one place.

Nobody passes a check by being signed out, deactivated or outside an
organisation. A superuser looks after the site from the admin pages and
belongs to no organisation, so has no role inside the app.
"""


def _role(user):
    """The person's role in their organisation, or None if they have none."""
    if not (user.is_authenticated and user.is_active and user.organisation_id):
        return None
    return user.role or None


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


def can_delete_comments(user):
    """Deleting a closed thread. Nobody can delete an open one."""
    return _has_role(user, "conductor", "librarian")
