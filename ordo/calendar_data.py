"""
Loading the published calendars in ordo/data/ into the database.

The files in ordo/data/romcal/ are exported once from romcal by
tools/calendar_export/export_romcal.js (see its README and
docs/acknowledgements.md). Each holds one calendar's occasions; a
national calendar holds only the days it adds or changes.

Loading is repeatable: each occasion is matched by its form, calendar
and key, and created or brought up to date. The data files are the
source for these rows, so an edit made to one in the admin is
overwritten on the next load. A conductor's own occasions have no key
and are never touched.
"""

import json
from pathlib import Path

from django.db import transaction

ROMCAL_DIR = Path(__file__).resolve().parent / "data" / "romcal"


def occasion_fields(item):
    """The model fields for one occasion in a data file."""
    fields = {
        "name": item["name"],
        "rank": item["rank"],
        "precedence": item["precedence"],
        "is_proper_of_time": item["is_proper_of_time"],
        "shares_with_memorials": item["shares_with_memorials"],
        "transfers": item["transfers"],
        "colour": item["colour"],
        "is_moveable": False,
        "easter_offset_days": None,
    }
    if "date_rule" in item:
        fields.update(
            date_rule=item["date_rule"],
            date_rule_args=item["date_rule_args"],
            date_offset_days=item["date_offset_days"],
            fixed_month=None,
            fixed_day=None,
        )
    else:
        fields.update(
            date_rule="",
            date_rule_args=[],
            date_offset_days=0,
            fixed_month=item["fixed_month"],
            fixed_day=item["fixed_day"],
        )
    return fields


@transaction.atomic
def load_calendar_files(directory=ROMCAL_DIR, calendar_use="current"):
    """Load every calendar file in a directory. Returns
    {calendar: (created, updated)}."""
    from .models import LiturgicalOccasion, LiturgicalSeason

    seasons = {}
    counts = {}
    for path in sorted(Path(directory).glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        created = updated = 0
        for item in data["occasions"]:
            fields = occasion_fields(item)
            if item["season"]:
                if item["season"] not in seasons:
                    seasons[item["season"]], _ = LiturgicalSeason.objects.get_or_create(name=item["season"])
                fields["season"] = seasons[item["season"]]
            else:
                fields["season"] = None
            _, was_created = LiturgicalOccasion.objects.update_or_create(
                calendar_use=calendar_use, calendar=data["calendar"], key=item["key"], defaults=fields
            )
            if was_created:
                created += 1
            else:
                updated += 1
        counts[data["calendar"]] = (created, updated)
    return counts
