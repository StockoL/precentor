"""
Link the existing settings row, if there is one, to the organisation the
shared rule picks. A brand-new database has no settings row yet, so
nothing happens there.
"""

from django.db import migrations

from accounts.migration_support import organisation_for_existing_rows


def give_settings_an_organisation(apps, schema_editor):
    SiteConfig = apps.get_model("core", "SiteConfig")
    unowned = SiteConfig.objects.filter(organisation__isnull=True)
    if unowned.exists():
        unowned.update(organisation=organisation_for_existing_rows(apps))


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0005_user_email_unique_ignoring_case"),
        ("core", "0009_settings_organisation"),
    ]

    operations = [
        migrations.RunPython(give_settings_an_organisation, migrations.RunPython.noop),
    ]
