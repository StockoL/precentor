from django.db import migrations


def to_catholic_seasons(apps, schema_editor):
    """
    Bring the seeded seasons into line with the Roman calendar.

    "Holy Week" becomes "Easter Triduum": Palm Sunday to Wednesday of
    Holy Week belong to Lent, and the Triduum is the season in its own
    right. Renaming the row (instead of deleting it) keeps any score
    already tagged with it.

    "Pentecost" goes: it is the solemnity that closes Eastertide, not a
    season. Scores tagged with it lose only that season tag; any
    occasion pointing at it keeps existing with season = NULL.
    """
    LiturgicalSeason = apps.get_model("ordo", "LiturgicalSeason")
    LiturgicalSeason.objects.filter(name="Holy Week").update(name="Easter Triduum")
    LiturgicalSeason.objects.filter(name="Pentecost").delete()


def from_catholic_seasons(apps, schema_editor):
    LiturgicalSeason = apps.get_model("ordo", "LiturgicalSeason")
    LiturgicalSeason.objects.filter(name="Easter Triduum").update(name="Holy Week")
    LiturgicalSeason.objects.get_or_create(name="Pentecost")


class Migration(migrations.Migration):

    dependencies = [
        ("ordo", "0007_relabel_calendar_use"),
    ]

    operations = [
        migrations.RunPython(to_catholic_seasons, from_catholic_seasons),
    ]
