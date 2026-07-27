from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect


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
