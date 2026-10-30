"""
Copy each service's Hymns and Psalm text into slots, as confirmed
reference pieces: confirmed, because that text is what the music list
printed. The hymns become one Hymns slot with a piece per hymn, in the
order typed; the psalm becomes one piece in a Psalm slot. A service that
already has a slot of that name gets the pieces in it.

The old fields are left as they were, so nothing is lost until a later
migration drops them. Historical models don't run the app's save(), so
the church, position and kind are set here.
"""

from django.db import migrations
from django.db.models import Max


def slot_called(service, name, kind, ServiceRole):
    slot = service.roles.filter(role_name__iexact=name).first()
    if slot is None:
        last = service.roles.aggregate(Max("position"))["position__max"] or 0
        slot = ServiceRole.objects.create(
            service=service, organisation_id=service.organisation_id,
            role_name=name, kind=kind, position=last + 1,
        )
    return slot


def copy_into_slots(apps, schema_editor):
    Service = apps.get_model("planning", "Service")
    ServiceRole = apps.get_model("planning", "ServiceRole")
    RolePiece = apps.get_model("planning", "RolePiece")

    def confirm(slot, reference):
        RolePiece.objects.create(
            service_role=slot, organisation_id=slot.organisation_id,
            reference=reference, is_confirmed=True,
        )

    for service in Service.objects.exclude(hymns="", psalm=""):
        hymns = [hymn.strip() for hymn in service.hymns.split(",") if hymn.strip()]
        if hymns:
            slot = slot_called(service, "Hymns", "hymn", ServiceRole)
            for hymn in hymns:
                confirm(slot, hymn)
        if service.psalm.strip():
            confirm(slot_called(service, "Psalm", "psalm", ServiceRole), service.psalm.strip())


class Migration(migrations.Migration):

    dependencies = [
        ("planning", "0022_piece_rule_message"),
    ]

    # Going back leaves the slots: the old fields still hold the text.
    operations = [
        migrations.RunPython(copy_into_slots, migrations.RunPython.noop),
    ]
