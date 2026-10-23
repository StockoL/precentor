"""
Making a new church. create_organisation() is the only way one comes into
being, whether through sign-up, the admin or the tests, so every church
starts the same: its settings and its own copies of the starter templates
and use types, which it can then change without touching anyone else's.
"""

from django.apps import apps
from django.db import transaction

from .models import Organisation

# Two slot templates for the services most churches sing.
STARTER_TEMPLATES = {
    "Mass": [
        "Introit",
        "Kyrie",
        "Gloria",
        "Gradual",
        "Alleluia or Tract",
        "Credo",
        "Offertory",
        "Sanctus",
        "Agnus Dei",
        "Communion",
    ],
    "Vespers": ["Psalms", "Hymn", "Magnificat", "Marian antiphon"],
}

STARTER_USE_TYPES = ["Mass", "Vespers", "General"]


@transaction.atomic
def create_organisation(name):
    """A new church with its settings and starter data, all or nothing."""
    # Looked up by name, as accounts sits beneath the apps that own these.
    SiteConfig = apps.get_model("core", "SiteConfig")
    SlotTemplate = apps.get_model("planning", "SlotTemplate")
    UseType = apps.get_model("ordo", "UseType")

    organisation = Organisation.objects.create(name=name)
    SiteConfig.of(organisation)
    SlotTemplate.objects.bulk_create(
        SlotTemplate(organisation=organisation, name=template, slot_names="\n".join(slots))
        for template, slots in STARTER_TEMPLATES.items()
    )
    UseType.objects.bulk_create(UseType(organisation=organisation, name=use_type) for use_type in STARTER_USE_TYPES)
    return organisation
