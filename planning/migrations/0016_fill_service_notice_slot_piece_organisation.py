"""
Give every existing service, notice, slot and piece its parent's
organisation, as their save() does from now on: a service and a notice
from their term, a slot from its service, a piece from its slot.

Each is one UPDATE with a subquery, parents first, so a slot reads its
service's organisation after the services have theirs.
"""

from django.db import migrations
from django.db.models import OuterRef, Subquery


def copy_from_parent(model, parent_model, parent_field):
    parents = parent_model.objects.filter(pk=OuterRef(parent_field)).values("organisation")[:1]
    model.objects.filter(organisation__isnull=True).update(organisation=Subquery(parents))


def give_children_their_parents_organisation(apps, schema_editor):
    get = apps.get_model
    copy_from_parent(get("planning", "Service"), get("planning", "Term"), "term")
    copy_from_parent(get("planning", "TermMarker"), get("planning", "Term"), "term")
    copy_from_parent(get("planning", "ServiceRole"), get("planning", "Service"), "service")
    copy_from_parent(get("planning", "RolePiece"), get("planning", "ServiceRole"), "service_role")


class Migration(migrations.Migration):
    dependencies = [
        ("planning", "0015_fill_term_and_template_organisation"),
    ]

    operations = [
        migrations.RunPython(give_children_their_parents_organisation, migrations.RunPython.noop),
    ]
