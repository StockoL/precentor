from django.utils.cache import patch_cache_control


class NoStoreWhenSignedInMiddleware:
    """
    Every response to someone signed in says Cache-Control: private,
    no-store, so neither the browser nor anything between it and the site
    keeps a copy of a church's pages, for the next person at a shared
    computer to find with the Back button. A response that has already
    chosen its own caching, such as the crest's year-long public cache,
    is left as it is.

    Signed in is decided before the view runs, so the page that logs
    someone out is covered too.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        signed_in = request.user.is_authenticated
        response = self.get_response(request)
        if signed_in and not response.has_header("Cache-Control"):
            patch_cache_control(response, private=True, no_store=True)
        return response
