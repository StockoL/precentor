"""
Loading the published calendars in ordo/data/ into the database.

The files are exported once by the scripts in tools/calendar_export/
(see its README and docs/acknowledgements.md): the Ordinary Form from
romcal into ordo/data/romcal/, and the 1962 calendar from Missalemeum
into ordo/data/missalemeum/. Each holds one calendar's occasions; a
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

DATA_DIR = Path(__file__).resolve().parent / "data"
ROMCAL_DIR = DATA_DIR / "romcal"
MISSALEMEUM_DIR = DATA_DIR / "missalemeum"
# Each folder of data files, and the form its occasions belong to.
SOURCES = ((ROMCAL_DIR, "current"), (MISSALEMEUM_DIR, "historic"))


def occasion_fields(item):
    """The model fields for one occasion in a data file."""
    fields = {
        "name": item["name"],
        "rank": item["rank"],
        "precedence": item.get("precedence", ""),
        "is_proper_of_time": item["is_proper_of_time"],
        "shares_with_memorials": item.get("shares_with_memorials", False),
        "transfers": item.get("transfers", []),
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
def load_calendar_files(sources=SOURCES):
    """Load every calendar file in each source folder. Returns
    {label: (created, updated)}, labelled by calendar, with "(1962)"
    after the 1962 ones."""
    seasons = {}
    counts = {}
    for directory, calendar_use in sources:
        for path in sorted(Path(directory).glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            if "occasions" not in data:
                continue  # the 1962 blocks, which aren't occasions
            label = data["calendar"] + (" (1962)" if calendar_use == "historic" else "")
            counts[label] = _load(data, calendar_use, seasons)
    return counts


def _load(data, calendar_use, seasons):
    """Create or update one file's occasions. Returns (created, updated)."""
    from .models import LiturgicalOccasion, LiturgicalSeason

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
    return created, updated
