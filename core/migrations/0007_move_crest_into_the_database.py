"""
Copy any crest stored as a file into the database, so nothing is lost when
the file field goes. Files on the old disk may already have been wiped by
a host, so a missing file is skipped rather than stopping the migration.

The fingerprint is worked out here, not with SiteConfig.set_crest():
a migration must keep working however the model changes later.
"""

import hashlib

from django.db import migrations

CONTENT_TYPES = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}


def move_crests(apps, schema_editor):
    SiteConfig = apps.get_model("core", "SiteConfig")
    for config in SiteConfig.objects.exclude(crest_image=""):
        try:
            with config.crest_image.open("rb") as image_file:
                data = image_file.read()
        except FileNotFoundError:
            continue
        extension = config.crest_image.name.rsplit(".", 1)[-1].lower()
        config.crest = data
        config.crest_type = CONTENT_TYPES.get(extension, "image/png")
        config.crest_version = hashlib.sha256(data).hexdigest()[:12]
        # Crests from the file field were always cropped to a banner.
        config.crest_style = "banner"
        config.save(update_fields=["crest", "crest_type", "crest_version", "crest_style"])


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0006_crest_style"),
    ]

    operations = [
        # Going back leaves the copies in place: the file field still has
        # its files, and the copies do no harm.
        migrations.RunPython(move_crests, migrations.RunPython.noop),
    ]
