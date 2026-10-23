from . import permissions

CHECKS = {
    "plan": permissions.can_plan,
    "edit_library": permissions.can_edit_library,
    "comment": permissions.can_comment,
    "manage_settings": permissions.can_manage_settings,
    "delete_comments": permissions.can_delete_comments,
    "manage_organisation": permissions.can_manage_organisation,
}


class Can(dict):
    """
    The permission checks, for templates: {% if can.plan %}. A template
    looks up can.plan as can["plan"] first, so each check runs only when a
    page asks for it, once per page however often it's used.
    """

    def __init__(self, user):
        super().__init__()
        self.user = user

    def __missing__(self, name):
        if name not in CHECKS:
            raise KeyError(name)
        self[name] = CHECKS[name](self.user)
        return self[name]


def can(request):
    # Not "perms": Django's auth context processor already uses that name.
    return {"can": Can(request.user)}
