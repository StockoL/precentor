"""
Split each template's slots, kept until now as lines of text, into
TemplateSlot rows, classified from their names. The name table is copied
here as it stood, as a migration has to do the same thing whenever it
runs. The text is left as it was, so nothing is lost until it's dropped.
"""

from django.db import migrations

NAMES = {
    "introit": ("proper", "introit"),
    "gradual": ("proper", "gradual"),
    "alleluia": ("proper", "alleluia"),
    "tract": ("proper", "tract"),
    "alleluia or tract": ("proper", "alleluia_or_tract"),
    "offertory": ("proper", "offertory"),
    "offertory antiphon": ("proper", "offertory"),
    "communion": ("proper", "communion"),
    "communion antiphon": ("proper", "communion"),
    "magnificat antiphon": ("antiphon", "magnificat_antiphon"),
    "kyrie": ("ordinary", ""),
    "gloria": ("ordinary", ""),
    "credo": ("ordinary", ""),
    "sanctus": ("ordinary", ""),
    "sanctus and benedictus": ("ordinary", ""),
    "agnus dei": ("ordinary", ""),
    "mass setting": ("ordinary", ""),
    "magnificat": ("canticle", ""),
    "nunc dimittis": ("canticle", ""),
    "benedictus": ("canticle", ""),
    "te deum": ("canticle", ""),
    "anthem": ("motet", ""),
    "organ": ("organ", ""),
}

LAST_WORDS = {
    "hymn": "hymn",
    "hymns": "hymn",
    "psalm": "psalm",
    "psalms": "psalm",
    "antiphon": "antiphon",
    "motet": "motet",
    "anthem": "motet",
    "voluntary": "organ",
    "prelude": "organ",
    "postlude": "organ",
}


def classify(name):
    name = " ".join(name.split()).lower()
    if name in NAMES:
        return NAMES[name]
    words = name.split()
    if words and words[-1] in LAST_WORDS:
        return LAST_WORDS[words[-1]], ""
    return "other", ""


def split_into_rows(apps, schema_editor):
    SlotTemplate = apps.get_model("planning", "SlotTemplate")
    TemplateSlot = apps.get_model("planning", "TemplateSlot")
    for template in SlotTemplate.objects.all():
        names = []
        for line in template.slot_names.splitlines():
            name = " ".join(line.split())
            if name and name.lower() not in (n.lower() for n in names):
                names.append(name)
        TemplateSlot.objects.bulk_create(
            TemplateSlot(
                template=template, organisation_id=template.organisation_id, name=name,
                kind=classify(name)[0], proper_part=classify(name)[1], position=position,
            )
            for position, name in enumerate(names, start=1)
        )


class Migration(migrations.Migration):

    dependencies = [
        ("planning", "0026_template_slot"),
    ]

    operations = [
        migrations.RunPython(split_into_rows, migrations.RunPython.noop),
    ]
