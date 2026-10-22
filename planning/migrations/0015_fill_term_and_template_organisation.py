"""
Give every existing term and slot template an organisation, so a later
migration can make the column required.

On a database with no organisations yet, such as a brand-new one, the
Mass and Vespers templates made by 0009 go if no service uses them: each
organisation gets its own copies when it registers. Anything in use is
kept and given an organisation like everything else.
"""

from django.db import migrations

from accounts.migration_support import no_organisations_yet, organisation_for_existing_rows


def give_terms_and_templates_an_organisation(apps, schema_editor):
    Term = apps.get_model("planning", "Term")
    SlotTemplate = apps.get_model("planning", "SlotTemplate")

    if no_organisations_yet(apps):
        SlotTemplate.objects.filter(organisation__isnull=True, services__isnull=True).delete()

    unowned_terms = Term.objects.filter(organisation__isnull=True)
    unowned_templates = SlotTemplate.objects.filter(organisation__isnull=True)
    if unowned_terms.exists() or unowned_templates.exists():
        church = organisation_for_existing_rows(apps)
        unowned_terms.update(organisation=church)
        unowned_templates.update(organisation=church)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0005_user_email_unique_ignoring_case"),
        ("planning", "0014_slot_and_piece_organisation"),
    ]

    operations = [
        # Going back leaves the organisations in place; deleted starter
        # templates aren't brought back, as a new organisation gets its own.
        migrations.RunPython(give_terms_and_templates_an_organisation, migrations.RunPython.noop),
    ]
