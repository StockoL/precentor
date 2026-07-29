from django.db import migrations

USE_TYPES = ["Eucharist", "General use", "Evening", "Harvest"]

SEASONS = {
    "cofe": [
        "Advent",
        "Christmas",
        "Epiphany",
        "Lent",
        "Passiontide",
        "Easter",
        "Ascensiontide",
        "Pentecost",
        "Trinity",
    ],
    "catholic": [
        "Advent",
        "Christmas",
        "Ordinary Time",
        "Lent",
        "Holy Week",
        "Easter",
        "Pentecost",
    ],
}


def seed(apps, schema_editor):
    UseType = apps.get_model("ordo", "UseType")
    LiturgicalSeason = apps.get_model("ordo", "LiturgicalSeason")

    for name in USE_TYPES:
        UseType.objects.get_or_create(name=name)

    for tradition, names in SEASONS.items():
        for name in names:
            LiturgicalSeason.objects.get_or_create(name=name, tradition=tradition)


def unseed(apps, schema_editor):
    UseType = apps.get_model("ordo", "UseType")
    LiturgicalSeason = apps.get_model("ordo", "LiturgicalSeason")

    UseType.objects.filter(name__in=USE_TYPES).delete()
    for tradition, names in SEASONS.items():
        LiturgicalSeason.objects.filter(tradition=tradition, name__in=names).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("ordo", "0003_liturgicalseason_usetype_and_more"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
