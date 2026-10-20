"""
One-off export of Missalemeum's 1962 calendar into Precentor.

Missalemeum (https://github.com/mmolenda/Missalemeum) is copyright 2022
Marcin Molenda, MIT licence. This script reads its calendar tables and
writes, into ordo/data/missalemeum/:

  general_1962.json            every day of the 1962 calendar, for
                               manage.py load_calendar
  blocks_1962.json             the order of the Proper of Time, which
                               ordo/calendar_1962.py lays out each year
  reference/general_1962.json  Missalemeum's resolved calendar for 2020
                               to 2040, which ordo's tests compare against

Run it with Missalemeum's backend on the path, in an environment with
its dependencies (see README.md):

  python export_missalemeum.py PATH/TO/Missalemeum/backend
"""

import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, sys.argv[1])

from api.constants import common  # noqa: E402
from api.constants.en.translation import TITLES  # noqa: E402
from api.constants.la import blocks  # noqa: E402
from api.kalendar.factory import MissalFactory  # noqa: E402

OUT_DIR = Path(__file__).resolve().parents[2] / "ordo" / "data" / "missalemeum"
YEARS = (2020, 2040)
SOURCE = (
    "Missalemeum (https://github.com/mmolenda/Missalemeum) at commit 75adfbb, "
    "copyright 2022 Marcin Molenda, MIT licence"
)

COLOURS = {"w": "white", "r": "red", "g": "green", "v": "violet", "p": "rose", "b": "black"}
SEASONS = {
    "Adv": "Advent",
    "Nat": "Christmas",
    "Epi": "Ordinary Time",
    "Quad": "Lent",
    "Pasc": "Easter",
    "Pent": "Ordinary Time",
}
TRIDUUM = {"Quad6-4", "Quad6-5", "Quad6-6"}


def key(observance_id):
    """'sancti:12-08:1:w' -> 'sancti:12-08': the day without its class
    and colour, which are fields of the occasion instead."""
    kind, name, _rank, _colour = observance_id.split(":")
    return f"{kind}:{name}"


def season(name):
    if name in TRIDUUM:
        return "Easter Triduum"
    if name.startswith("Quadp"):
        return None  # Septuagesima: before Lent, not part of it
    if name.startswith("093"):
        return "Ordinary Time"  # the September Ember Days, after Pentecost
    prefix = re.match(r"[A-Za-z]+", name)
    return SEASONS.get(prefix.group(0)) if prefix else None


def occasion(observance_id):
    kind, name, rank, colour = observance_id.split(":")
    item = {
        "key": key(observance_id),
        "name": TITLES[observance_id],
        "rank": f"class_{rank}",
        "is_proper_of_time": kind == "tempora",
        "colour": COLOURS[colour[0]],
        "season": season(name) if kind == "tempora" else None,
    }
    if kind == "tempora":
        item.update(date_rule="tempora_1962", date_rule_args=[name], date_offset_days=0)
    elif name == "10-DU":
        # Christ the King, the last Sunday of October.
        item.update(date_rule="christ_the_king_1962", date_rule_args=[], date_offset_days=0)
    else:
        month, day = re.match(r"(\d\d)-(\d\d)", name).groups()
        item.update(fixed_month=int(month), fixed_day=int(day))
    return item


def block(rows):
    return [[key(i) for i in row] for row in rows]


def in_scope(observance_id):
    """Calendar days of the first three classes; not the commons, the
    plain feria or the fourth class."""
    kind, _name, rank, _colour = observance_id.split(":")
    return kind in ("tempora", "sancti") and rank in ("1", "2", "3")


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def write_reference(path, header, days):
    path.parent.mkdir(parents=True, exist_ok=True)
    head = [f" {json.dumps(k)}: {json.dumps(v)}," for k, v in header.items()]
    lines = [f"  {json.dumps(d)}: {json.dumps(ids)}" for d, ids in days.items()]
    path.write_text("{\n" + "\n".join(head) + '\n "days": {\n' + ",\n".join(lines) + "\n }\n}\n", encoding="utf-8")


def main():
    tempora_ids = {i for row in blocks.TEMPORA_IDS for i in ([row] if isinstance(row, str) else row)}
    all_ids = sorted(tempora_ids | set(blocks.SANCTI) | {common.TEMPORA_NAT2_0, common.SANCTI_10_DU})
    occasions = [occasion(i) for i in all_ids if i.split(":")[0] in ("tempora", "sancti")]
    write_json(OUT_DIR / "general_1962.json", {"source": SOURCE, "calendar": "general_roman", "occasions": occasions})

    write_json(OUT_DIR / "blocks_1962.json", {
        "source": SOURCE,
        "post_epiphany": block(blocks.POST_EPIPHANY),
        "from_pre_lent_to_post_pentecost": block(blocks.FROM_PRE_LENT_TO_POST_PENTECOST),
        "week_24_after_pentecost": block(blocks.WEEK_24_AFTER_PENTECOST),
        "advent": block(blocks.ADVENT),
        "ember_days_september": block(blocks.EMBER_DAYS_SEPTEMBER),
        "nativity_octave_sunday": block(blocks.NATIVITY_OCTAVE_SUNDAY),
        "nativity_octave_feria": block(blocks.NATIVITY_OCTAVE_FERIA),
        "holy_name": key(common.TEMPORA_NAT2_0),
        "christ_the_king": key(common.SANCTI_10_DU),
    })

    days = {}
    for year in range(YEARS[0], YEARS[1] + 1):
        calendar = MissalFactory().create(year)
        day = date(year, 1, 1)
        while day.year == year:
            entry = calendar.get_day(day)
            ids = [o.id for o in entry.celebration] + [o.id for o in entry.commemoration]
            kept = [key(i) for i in ids if in_scope(i)]
            if kept:
                days[day.isoformat()] = kept
            day += timedelta(days=1)
    write_reference(OUT_DIR / "reference" / "general_1962.json", {
        "source": SOURCE + "; resolved calendars, fourth class and commons removed",
        "calendar": "general_roman",
        "years": list(YEARS),
    }, days)
    print(f"{len(occasions)} occasions, {len(days)} reference days")


if __name__ == "__main__":
    main()
