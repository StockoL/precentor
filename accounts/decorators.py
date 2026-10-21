from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


def role_required(check):
    """
    Guard a function view with one of the checks in accounts.permissions:

        @role_required(can_plan)
        def add_role(request, service_pk): ...

    Someone signed out goes to the login page and comes back afterwards.
    Someone signed in without the right gets a 403. Django's own
    user_passes_test sends them to the login page too, where logging in
    again changes nothing, so it looks like a loop.
    """

    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not check(request.user):
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return wrapper

    return decorator
