from django.core.management.base import BaseCommand

from ordo.calendar_data import load_calendar_files


class Command(BaseCommand):
    help = (
        "Load the published calendars in ordo/data/ (General Roman, England "
        "and Wales) into the database. Safe to run again: existing rows are "
        "brought up to date and occasions entered by hand are left alone."
    )

    def handle(self, *args, **options):
        for calendar, (created, updated) in load_calendar_files().items():
            self.stdout.write(f"{calendar}: {created} added, {updated} updated")
