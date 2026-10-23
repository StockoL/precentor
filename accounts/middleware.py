class OrganisationMiddleware:
    """
    Sets request.organisation: the signed-in person's organisation, or None
    for someone signed out or a superuser, who belongs to none. It comes
    only from the person, never from the session, the address or a form,
    so nobody can choose which church's data they see.

    The person is loaded with their organisation in one query (see
    accounts.backends), so this costs nothing extra.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        request.organisation = user.organisation if user.is_authenticated else None
        return self.get_response(request)
