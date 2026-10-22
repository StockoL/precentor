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

    It's set as the form is built, before the form checks anything, so a
    form can check its data against the church's own, such as a template
    name the church already uses.
    """

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.instance.organisation = self.request.user.organisation
        return form
