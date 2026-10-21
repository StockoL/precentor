from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect
from django.utils.cache import add_never_cache_headers


class DeletePageMixin:
    """
    For "Delete …?" pages. Two things go wrong after a delete if nothing
    stops them: the browser's Back button shows the cached confirmation
    again, and confirming it a second time finds nothing to delete and
    shows "Page not found". So the page is never cached, and if the thing
    has already gone, the visitor goes back to its list with a message
    saying so, whether they arrive by Back, a bookmark or a second click.

    Set gone_url (a URL or a reverse_lazy) and gone_message on the view.
    Put it after any permission mixin, so access is checked first.
    """

    gone_url = None
    gone_message = "That has already been deleted."

    def dispatch(self, request, *args, **kwargs):
        try:
            self.get_object()
        except Http404:
            messages.info(request, self.gone_message)
            return redirect(self.gone_url)
        response = super().dispatch(request, *args, **kwargs)
        add_never_cache_headers(response)
        return response
