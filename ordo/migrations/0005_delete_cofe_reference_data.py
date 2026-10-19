from django.db import migrations


def delete_cofe_rows(apps, schema_editor):
    """
    Precentor is Catholic-only from this point. Remove the Church of
    England reference data *before* the next migration drops the
    ``tradition`` columns, because once the column is gone there is no
    way to tell which rows were CofE.

    Deleting an occasion is safe for related data: Service.occasion is
    SET_NULL, and the many-to-many links (Service.additional_occasions,
    Score.suited_occasions, Score.suited_seasons) are just join rows that
    go with it. Occasions whose season is deleted keep existing with
    season = NULL.
    """
    LiturgicalOccasion = apps.get_model("ordo", "LiturgicalOccasion")
    LiturgicalSeason = apps.get_model("ordo", "LiturgicalSeason")

    LiturgicalOccasion.objects.filter(tradition="cofe").delete()
    LiturgicalSeason.objects.filter(tradition="cofe").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("ordo", "0004_seed_use_types_and_seasons"),
    ]

    operations = [
        # No reverse: the CofE rows are intentionally gone for good.
        migrations.RunPython(delete_cofe_rows, migrations.RunPython.noop),
    ]
