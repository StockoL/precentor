"""
Give every existing score an organisation, so a later migration can make
the column required. Which organisation is decided by
accounts.migration_support, the same for every app.
"""

from django.db import migrations

from accounts.migration_support import organisation_for_existing_rows


def give_scores_an_organisation(apps, schema_editor):
    Score = apps.get_model("library", "Score")
    unowned = Score.objects.filter(organisation__isnull=True)
    if unowned.exists():
        unowned.update(organisation=organisation_for_existing_rows(apps))


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0005_user_email_unique_ignoring_case"),
        ("library", "0015_score_organisation"),
    ]

    operations = [
        # Going back leaves the organisation in place; the column still
        # allows it.
        migrations.RunPython(give_scores_an_organisation, migrations.RunPython.noop),
    ]
