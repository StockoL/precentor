"""
Precentor's calendar against romcal's, every day from 2020 to 2040.

ordo/data/romcal/reference/ holds romcal's resolved calendars, exported
with the data (tools/calendar_export/). Precentor agrees with them except
on the days listed below, each explained in docs/calendar_plan.md,
section 4.
"""

import json
from datetime import date

from django.test import TestCase

from .calendar import resolve_year
from .calendar_data import ROMCAL_DIR, load_calendar_files
from .models import LiturgicalOccasion

# Days where Precentor and romcal keep different celebrations:
# {day: ([Precentor's celebration], [romcal's])}. Holy Thursday, where
# only the order differs, is checked separately. The reasons:
#
# MOVED: romcal drops an impeded solemnity; Precentor moves it to the
#   next free day (General Norms, no. 60).
# SORTING: romcal sorts a memorial that may share its day (the Immaculate
#   Heart) above everything, even a solemnity or a feast.
# TRANSFER: romcal counts a move "to the day after Divine Mercy Sunday"
#   or "the day before Palm Sunday" from the original date.
# TIE: two feasts of the same level; the norms don't settle it, and
#   Precentor puts the one that moves with the seasons first.
JOHN = "nativity_of_john_the_baptist"
HEART = "immaculate_heart_of_mary"
GEORGE = "george_of_lydda_martyr"
DAVID = "david_of_wales_bishop"
JOSEPH = "joseph_spouse_of_mary"

SAME_IN_EVERY_CALENDAR = {
    "2022-06-25": ([JOHN], [HEART]),  # MOVED from the Sacred Heart, 24 June
    "2028-06-24": ([JOHN], [HEART]),  # SORTING
    "2033-06-25": ([JOHN], [HEART]),  # MOVED from the Sacred Heart
    "2038-07-03": (["thomas_apostle"], [HEART]),  # SORTING
}

KNOWN_DIFFERENCES = {
    "general_roman": {
        **SAME_IN_EVERY_CALENDAR,
        "2030-06-29": (["peter_and_paul_apostles"], [HEART]),  # SORTING
        "2035-03-17": ([JOSEPH], ["lent_5_saturday"]),  # TRANSFER
        "2038-06-25": ([JOHN], []),  # MOVED from Corpus Christi, 24 June
    },
    "england": {
        **SAME_IN_EVERY_CALENDAR,
        "2021-05-27": (["our_lord_jesus_christ_the_eternal_high_priest"], ["augustine_of_canterbury_bishop"]),  # TIE
        "2022-04-25": ([GEORGE], ["mark_evangelist"]),  # TRANSFER
        "2023-04-24": ([GEORGE], []),  # MOVED from the Third Sunday of Easter
        "2025-04-28": ([GEORGE], []),  # TRANSFER
        "2030-04-29": ([GEORGE], ["catherine_of_siena_virgin"]),  # TRANSFER
        "2033-04-25": ([GEORGE], ["mark_evangelist"]),  # TRANSFER
        "2034-04-24": ([GEORGE], []),  # MOVED from the Second Sunday of Easter
        "2035-03-17": ([JOSEPH], ["patrick_of_ireland_bishop"]),  # TRANSFER
        "2038-05-03": ([GEORGE], ["philip_and_james_apostles"]),  # TRANSFER
    },
    "wales": {
        **SAME_IN_EVERY_CALENDAR,
        "2020-03-02": ([DAVID], ["lent_1_monday"]),  # MOVED from a Sunday of Lent
        "2026-03-02": ([DAVID], ["lent_2_monday"]),  # MOVED
        "2028-03-02": ([DAVID], ["thursday_after_ash_wednesday"]),  # MOVED from Ash Wednesday
        "2035-03-17": ([JOSEPH], ["lent_5_saturday"]),  # TRANSFER
        "2037-03-02": ([DAVID], ["lent_2_monday"]),  # MOVED
    },
}


def reference_days(calendar):
    path = ROMCAL_DIR / "reference" / f"{calendar}.json"
    return json.loads(path.read_text(encoding="utf-8"))["days"]


class RomcalReferenceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        load_calendar_files()

    def precentor_days(self, calendar):
        days = {}
        for year in range(2020, 2041):
            for day, occasions in resolve_year(year, "current", calendar).items():
                days[day.isoformat()] = [o.key for o in occasions]
        return days

    def test_every_day_agrees_except_the_known_differences(self):
        for calendar, known in KNOWN_DIFFERENCES.items():
            with self.subTest(calendar=calendar):
                ours, theirs = self.precentor_days(calendar), reference_days(calendar)
                differences = {}
                for day in sorted(set(ours) | set(theirs)):
                    mine, romcal = ours.get(day, []), theirs.get(day, [])
                    if mine == romcal:
                        continue
                    if "thursday_of_the_lords_supper" in mine and set(mine) == set(romcal):
                        continue  # Holy Thursday: same days, Precentor's order
                    differences[day] = (mine[:1], romcal[:1])
                self.assertEqual(differences, known)

    def test_holy_thursday_lists_the_lords_supper_first(self):
        days = self.precentor_days("general_roman")
        self.assertEqual(days["2026-04-02"], ["thursday_of_the_lords_supper", "holy_thursday"])
