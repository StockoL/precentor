"""
A read-only check, for the day the work since submission is merged: run
it against the live data after migrating, before the old columns are
dropped. It changes nothing.
"""

from django.core.management.base import BaseCommand, CommandError

from core.models import SiteConfig
from planning.models import Service, SlotTemplate


def hymns_typed(service):
    """The hymns as the old field held them, in the order typed."""
    return [hymn.strip() for hymn in service.hymns.split(",") if hymn.strip()]


def confirmed_references(service, slot_name):
    slot = service.roles.filter(role_name__iexact=slot_name).first()
    if slot is None:
        return []
    return list(slot.pieces.filter(is_confirmed=True, reference__gt="").order_by("pk").values_list(
        "reference", flat=True))


def names_typed(template):
    """A template's slots as the old text held them: each name once,
    whatever its case, in order."""
    names = []
    for line in template.slot_names.splitlines():
        name = " ".join(line.split())
        if name and name.lower() not in (n.lower() for n in names):
            names.append(name)
    return names


class Command(BaseCommand):
    help = (
        "Check that every service's hymns and psalm, and every template's "
        "slots, were copied into their new form, and list churches that "
        "had hymns and the psalm hidden on the music list. Changes nothing."
    )

    def handle(self, *args, **options):
        problems = []
        services = Service.objects.exclude(hymns="", psalm="").select_related("term")
        for service in services:
            where = f"{service.term.organisation} / {service} (service {service.pk})"
            typed = hymns_typed(service)
            # The copied pieces come first in their slot, in the typed order.
            copied = confirmed_references(service, "Hymns")[: len(typed)]
            if copied != typed:
                problems.append(f"{where}: hymns {typed} but the Hymns slot has {copied}")
            psalm = service.psalm.strip()
            if psalm and psalm not in confirmed_references(service, "Psalm"):
                problems.append(f"{where}: psalm {psalm!r} isn't confirmed in the Psalm slot")

        templates = SlotTemplate.objects.select_related("organisation")
        for template in templates:
            rows = list(template.template_slots.order_by("position").values_list("name", flat=True))
            if rows != names_typed(template):
                problems.append(
                    f"{template.organisation} / template {template.name!r}: text {names_typed(template)} "
                    f"but rows {rows}"
                )

        self.stdout.write(
            f"Checked {services.count()} services with hymns or a psalm, and {templates.count()} templates."
        )
        # On the submitted site a church could keep hymns and the psalm off
        # its music list; nothing reads that setting now, so they'd appear.
        hidden = SiteConfig.objects.filter(show_hymns_psalm=False).select_related("organisation")
        for config in hidden:
            count = Service.objects.filter(term__organisation=config.organisation).exclude(hymns="", psalm="").count()
            if count:
                self.stdout.write(self.style.WARNING(
                    f"{config.organisation} hid hymns and the psalm on its music list, and {count} of its "
                    "services had some: they'll now be printed. Tell the church, or remove those pieces."
                ))
        for problem in problems:
            self.stdout.write(self.style.ERROR(problem))
        if problems:
            raise CommandError(f"{len(problems)} problem(s): don't drop the old columns yet.")
        self.stdout.write(self.style.SUCCESS("Everything was copied. The old columns can be dropped."))
