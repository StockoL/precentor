"""
Shared by the migrations that give existing rows an organisation, so every
app's migration picks the same one.

Deployed migrations depend on how this behaves, so don't change it: if a
later migration needs a different rule, give it a new function.
"""


class SeveralOrganisationsError(Exception):
    pass


def no_organisations_yet(apps):
    """True on a database where no organisation has been made, such as a
    brand-new one. Starter rows nothing uses can then simply go, since each
    organisation gets its own copies when it registers."""
    return not apps.get_model("accounts", "Organisation").objects.exists()


def organisation_for_existing_rows(apps):
    """
    Where existing rows go. With one organisation, it's that one. With none,
    a new one called "My church", which can be renamed in the admin; it's
    only made when a row needs it, so call this only then. With several,
    there's no safe guess, so the migration stops.
    """
    Organisation = apps.get_model("accounts", "Organisation")
    organisations = list(Organisation.objects.all()[:2])
    if len(organisations) > 1:
        raise SeveralOrganisationsError(
            "There is more than one organisation, so it isn't clear which one "
            "existing rows belong to. Give them an organisation by hand, then migrate again."
        )
    if organisations:
        return organisations[0]
    return Organisation.objects.create(name="My church")
