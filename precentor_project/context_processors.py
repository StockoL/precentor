from accounts.mixins import ConductorRequiredMixin
from comments.models import Comment

# URL namespace -> nav section, and each section's own landing page.
NAV_SECTIONS = {
    "planning": ("terms", "term_list"),
    "library": ("library", "score_list"),
    "comments": ("inbox", "inbox"),
    "core": ("settings", "site_config_update"),
}


def nav_current(request):
    """
    Which nav link to mark with aria-current, and how: "page" on the
    section's own landing page, "true" anywhere else in that section
    (a service page sits under Terms, for example).
    """
    match = request.resolver_match
    if match is None or match.namespace not in NAV_SECTIONS:
        return {}
    section, landing = NAV_SECTIONS[match.namespace]
    return {section: "page" if match.url_name == landing else "true"}


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
        # Same set the inbox page lists: every open comment.
        "open_comment_count": Comment.objects.filter(is_open=True).count(),
        "nav_current": nav_current(request),
    }
