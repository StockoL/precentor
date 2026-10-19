from django.db import migrations

# Old seeded name -> the name a Catholic choir uses for the same thing.
RENAMES = {
    "Eucharist": "Mass",
    "Evening": "Vespers",
}


def to_catholic_names(apps, schema_editor):
    """
    Rename instead of delete-and-recreate, so any score already tagged
    with the old use type keeps its tag under the new name.
    """
    UseType = apps.get_model("ordo", "UseType")
    for old, new in RENAMES.items():
        UseType.objects.filter(name=old).update(name=new)


def from_catholic_names(apps, schema_editor):
    UseType = apps.get_model("ordo", "UseType")
    for old, new in RENAMES.items():
        UseType.objects.filter(name=new).update(name=old)


class Migration(migrations.Migration):

    dependencies = [
        ("ordo", "0009_remove_harvest_use_type"),
    ]

    operations = [
        migrations.RunPython(to_catholic_names, from_catholic_names),
    ]
