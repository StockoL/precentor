from django.db import migrations


def create_groups(apps, _schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.get_or_create(name="Conductor")
    Group.objects.get_or_create(name="Librarian")


def remove_groups(apps, _schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name__in=["Conductor", "Librarian"]).delete()


class Migration(migrations.Migration):
    dependencies = [  # noqa
        ("auth", "0001_initial"),
    ]
    operations = [  # noqa
        migrations.RunPython(create_groups, remove_groups),
    ]
