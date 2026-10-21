from django.core.management.base import BaseCommand

from ordo.calendar_data import load_calendar_files


class Command(BaseCommand):
    help = (
        "Load the published calendars in ordo/data/ (General Roman, England "
        "and Wales) into the database. Safe to run again: existing rows are "
        "brought up to date, rows gone from the files are removed unless in "
        "use, and occasions entered by hand are left alone."
    )

    def handle(self, *args, **options):
        for calendar, result in load_calendar_files().items():
            line = f"{calendar}: {result.created} added, {result.updated} updated"
            if result.removed:
                line += f", {result.removed} removed"
            self.stdout.write(line)
            for occasion in result.kept_in_use:
                self.stdout.write(self.style.WARNING(
                    f"  Kept {occasion.name} ({occasion.key}): no longer in the data, but a service "
                    "or score uses it. Change those to another occasion, then load again to remove it."
                ))
