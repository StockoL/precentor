"""
Give every existing comment the organisation of what it's about, as its
save() does from now on. A comment's subject can be a term, a service or a
piece, so the comments are taken a kind of subject at a time: for each
kind, one UPDATE copies the organisation across with a subquery.

It runs after the planning fill-ins, so every subject already has one.
"""

from django.db import migrations
from django.db.models import OuterRef, Subquery


def give_comments_their_subjects_organisation(apps, schema_editor):
    Comment = apps.get_model("comments", "Comment")
    ContentType = apps.get_model("contenttypes", "ContentType")
    unowned = Comment.objects.filter(organisation__isnull=True)
    for content_type in ContentType.objects.filter(pk__in=unowned.values("content_type")):
        Subject = apps.get_model(content_type.app_label, content_type.model)
        subjects = Subject.objects.filter(pk=OuterRef("object_id")).values("organisation")[:1]
        unowned.filter(content_type=content_type).update(organisation=Subquery(subjects))


class Migration(migrations.Migration):
    dependencies = [
        ("comments", "0003_comment_organisation"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("planning", "0016_fill_service_notice_slot_piece_organisation"),
    ]

    operations = [
        migrations.RunPython(give_comments_their_subjects_organisation, migrations.RunPython.noop),
    ]
