"""
Give every existing use type an organisation, so a later migration can
make the column required.

On a database with no organisations yet, such as a brand-new one, the use
types made by 0004 and 0010 (Mass, Vespers, General use) go if no score is
tagged with them: each organisation gets its own copies when it
registers. Any a score uses are kept and given an organisation like
everything else, so no score loses a tag.
"""

from django.db import migrations

from accounts.migration_support import no_organisations_yet, organisation_for_existing_rows


def give_use_types_an_organisation(apps, schema_editor):
    UseType = apps.get_model("ordo", "UseType")

    if no_organisations_yet(apps):
        UseType.objects.filter(organisation__isnull=True, suited_scores__isnull=True).delete()

    unowned = UseType.objects.filter(organisation__isnull=True)
    if unowned.exists():
        unowned.update(organisation=organisation_for_existing_rows(apps))


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0005_user_email_unique_ignoring_case"),
        ("library", "0016_fill_score_organisation"),
        ("ordo", "0016_use_type_organisation"),
    ]

    operations = [
        # Going back leaves the organisations in place; deleted starter use
        # types aren't brought back, as a new organisation gets its own.
        migrations.RunPython(give_use_types_an_organisation, migrations.RunPython.noop),
    ]
