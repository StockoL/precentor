from django.db import migrations

# The two templates every installation starts with. A conductor can edit
# or delete them; this runs once, so it never undoes their changes.
TEMPLATES = {
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
    "Vespers": [
        "Psalms",
        "Hymn",
        "Magnificat",
        "Marian antiphon",
    ],
}


def add_templates(apps, schema_editor):
    SlotTemplate = apps.get_model("planning", "SlotTemplate")
    for name, slots in TEMPLATES.items():
        SlotTemplate.objects.get_or_create(name=name, defaults={"slot_names": "\n".join(slots)})


def remove_templates(apps, schema_editor):
    SlotTemplate = apps.get_model("planning", "SlotTemplate")
    SlotTemplate.objects.filter(name__in=TEMPLATES).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("planning", "0008_slot_template"),
    ]

    operations = [
        migrations.RunPython(add_templates, remove_templates),
    ]
