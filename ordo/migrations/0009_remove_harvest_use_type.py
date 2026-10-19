from django.db import migrations


def remove_harvest(apps, schema_editor):
    """
    Harvest Festival is a Church of England custom with no place in the
    Roman calendar, so it no longer belongs in the seeded use types.
    Scores tagged with it lose only that tag.
    """
    UseType = apps.get_model("ordo", "UseType")
    UseType.objects.filter(name="Harvest").delete()


def restore_harvest(apps, schema_editor):
    UseType = apps.get_model("ordo", "UseType")
    UseType.objects.get_or_create(name="Harvest")


class Migration(migrations.Migration):

    dependencies = [
        ("ordo", "0008_catholic_seasons"),
    ]

    operations = [
        migrations.RunPython(remove_harvest, restore_harvest),
    ]
