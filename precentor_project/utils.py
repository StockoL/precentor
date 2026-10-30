from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme


def ajax_or_redirect(request, fragments, redirect_url, error_message=None, status=200):
    """
    Common response tail for an AJAX-capable action view. Fragment
    selection stays view-specific (each action knows what it changed);
    this only centralizes the is-this-AJAX branch so it's written once.
    """
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"fragments": fragments}, status=status)
    if error_message:
        messages.error(request, error_message)
    return redirect(redirect_url)


def safe_next(request, value):
    """
    value if it's a page on this site, else "". For a ?next= address to go
    back to after a form: anything else (javascript:, another site) must
    never be redirected to or written into a link.
    """
    if value and url_has_allowed_host_and_scheme(
        value, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return value
    return ""
