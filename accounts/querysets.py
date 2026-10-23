from django.db import models


class OrganisationQuerySet(models.QuerySet):
    """
    For the models that hold a church's own data. Views ask for
    Model.objects.for_organisation(request.organisation) rather than
    Model.objects.all(), so a person only ever reaches their own church's
    rows. With no organisation (signed out, or a superuser) it finds
    nothing, since every row has one.
    """

    def for_organisation(self, organisation):
        return self.filter(organisation=organisation)


def own(model, request):
    """The request's church's own rows of a model, for looking one up from
    an address: get_object_or_404(own(Term, request), pk=term_pk)."""
    return model.objects.for_organisation(request.organisation)
