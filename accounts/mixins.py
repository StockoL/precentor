from django.contrib.auth.mixins import UserPassesTestMixin


class RoleRequiredMixin(UserPassesTestMixin):
    """
    Guard a class-based view with one of the checks in accounts.permissions:

        class TermCreateView(RoleRequiredMixin, CreateView):
            permission = can_plan

    Like role_required: signed out goes to log in, signed in without the
    right gets a 403. UserPassesTestMixin already tells those two apart.

    Pages that only show things still use LoginRequiredMixin, so anyone
    signed in can read everything. That is only safe while there is one
    organisation; Stage B limits reading to a person's own organisation.
    """

    permission = None

    def test_func(self):
        # Through the class, not self: a function stored on a class becomes
        # a method when read through an instance, and would get the view as
        # its user.
        return type(self).permission(self.request.user)


class OrganisationCreateMixin:
    """
    For the create views of what a church owns directly (terms, scores,
    slot templates): the new thing belongs to the signed-in person's
    organisation. It comes from the person, never from the form, so nobody
    can put something into another church's data by editing a field.

    The new thing is given to the form already belonging to the church, so
    the form knows the church from the start: it can offer only the
    church's own choices and check its data against the church's own, such
    as a template name already in use.
    """

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.model(organisation=self.request.organisation)
        return kwargs


class OrganisationScopedMixin:
    """
    For list, detail, edit and delete views of a church's data: only rows
    belonging to the person's organisation are found. Another church's row
    is simply not there, so Django answers 404, not 403, and nobody learns
    that it exists.
    """

    def get_queryset(self):
        return super().get_queryset().for_organisation(self.request.organisation)
