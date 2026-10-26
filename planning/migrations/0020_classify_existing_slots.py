"""
Classify the slots made before slots had kinds. The name table is copied
here, as it stood when this migration was written, rather than imported
from planning.slot_kinds: a migration has to do the same thing whenever it
runs, even after the table in the app has grown.
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


def classify_existing(apps, schema_editor):
    ServiceRole = apps.get_model("planning", "ServiceRole")
    for slot in ServiceRole.objects.filter(kind=""):
        slot.kind, slot.proper_part = classify(slot.role_name)
        slot.save(update_fields=["kind", "proper_part"])


class Migration(migrations.Migration):

    dependencies = [
        ("planning", "0019_slot_kind_and_proper_part"),
    ]

    # Going back needs nothing undone: the fields themselves go with 0019.
    operations = [
        migrations.RunPython(classify_existing, migrations.RunPython.noop),
    ]
