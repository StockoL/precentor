from accounts.mixins import ConductorRequiredMixin


def nav(request):
    """
    Values the site nav in base.html needs on every page. A context
    processor runs for every template rendered with a request, so each
    view doesn't have to add these itself. It lives at project level
    because it draws on more than one app.
    """
    user = request.user
    if not user.is_authenticated:
        return {}
    return {
        "is_conductor": ConductorRequiredMixin.is_conductor(user),
    }
