"""
Importing a library from a spreadsheet saved as CSV, in Precentor's own
format: one score per row, under the headers in COLUMNS. Nothing here
touches a request or a page, so it can be tested with plain strings.

First the file is read: decoded, its separator worked out and its
headers matched. A file that can't work at all, such as one missing a
required column, stops with ImportProblem before any row is looked at.
Then each row is checked by the same rules as the score form, and the
rows that fail are kept with the reason, to show the person.
"""

import csv
import io
import re
from dataclasses import dataclass
from dataclasses import field as dataclass_field

from django import forms

from .models import Score

# The columns, in the order the template gives them: (header, score field,
# required). The template, the header check and the instructions all read
# this list, so they can't drift apart.
COLUMNS = [
    ("Title", "title", True),
    ("Composer surname", "composer_surname", True),
    ("Composer other names", "composer_other_names", False),
    ("Arranger", "arranger", False),
    ("Editor", "editor", False),
    ("Voicing", "voicing", False),
    ("Language", "language", False),
    ("Copies owned", "copies_owned", False),
    ("Filing location", "filing_location", False),
    ("Duration (minutes)", "duration_minutes", False),
    ("Last sung", "last_sung_manual", False),
]

MAX_BYTES = 2 * 1024 * 1024
MAX_ROWS = 5000
SEPARATORS = (",", ";", "\t")


class ImportProblem(Exception):
    """The file as a whole can't be imported; the message says why."""


def decode(data):
    """
    The file's text, and whether it had to be read as Windows-1252. Excel
    saves CSV UTF-8 with a byte-order mark, which utf-8-sig drops; older
    Excel saves plain "CSV" as Windows-1252, which is tried second so the
    result page can say accents may need checking.
    """
    try:
        return data.decode("utf-8-sig"), False
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace"), True


def separator(header_line):
    """Comma, semicolon or tab, whichever the header line uses most.
    European Excel saves with semicolons, and tabs come from pasting."""
    return max(SEPARATORS, key=header_line.count)


def tidy(header):
    """A header as it's compared: capitals and spacing don't matter."""
    return " ".join(header.split()).casefold()


def read_rows(data):
    """
    The file's rows as dictionaries keyed by score field, each with the
    row number a person sees in their spreadsheet (the header is row 1),
    plus whether it was read as Windows-1252 and the headers that weren't
    recognised. Blank rows are left out.
    """
    if len(data) > MAX_BYTES:
        raise ImportProblem("The file is larger than 2 MB. Split it into smaller files and import each.")
    text, fallback = decode(data)
    lines = text.splitlines()
    if not lines or not lines[0].strip():
        raise ImportProblem("The file is empty, or its first line has no headers.")

    reader = csv.reader(io.StringIO(text), delimiter=separator(lines[0]))
    headers = next(reader)
    known = {tidy(header): field for header, field, _ in COLUMNS}
    positions = {}
    ignored = []
    for position, header in enumerate(headers):
        field = known.get(tidy(header))
        if field and field not in positions:
            positions[field] = position
        elif header.strip():
            ignored.append(header.strip())
    missing = [header for header, field, required in COLUMNS if required and field not in positions]
    if missing:
        raise ImportProblem(
            f"The file has no {' or '.join(missing)} column. "
            "Download the template to see the headers Precentor expects."
        )

    rows = []
    for number, cells in enumerate(reader, start=2):
        if not any(cell.strip() for cell in cells):
            continue
        if len(rows) == MAX_ROWS:
            raise ImportProblem(f"The file has more than {MAX_ROWS:,} scores. Split it and import each part.")
        values = {field: (cells[position].strip() if position < len(cells) else "")
                  for field, position in positions.items()}
        rows.append((number, values))
    return rows, fallback, ignored


# Checking each row.

class ScoreImportRowForm(forms.ModelForm):
    """
    One row, checked by the same rules as the score form: lengths, whole
    numbers and the model's own clean(). Copies owned may be blank (0), and
    the last-sung date may be written either way round.
    """

    class Meta:
        model = Score
        fields = [field for _, field, _ in COLUMNS]  # noqa

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["copies_owned"].required = False
        self.fields["last_sung_manual"].input_formats = ["%Y-%m-%d", "%d/%m/%Y"]
        self.fields["last_sung_manual"].error_messages["invalid"] = "write it as 2026-03-15 or 15/03/2026"

    def clean_copies_owned(self):
        return self.cleaned_data["copies_owned"] or 0


# A voicing made only of S, A, T and B (with separators) says how many
# parts of each there are; anything else, such as "Unison", doesn't.
PLAIN_VOICING = re.compile(r"^[SATB]+([.\s/+-][SATB]+)*$")


def parts_from_voicing(score):
    """Fill in the part counts from a plain voicing, as the spreadsheet has
    no columns for them, so "any four-part mixed" finds imported scores
    too: SSATB is 2, 1, 1, 1 and SATB.SATB is 2, 2, 2, 2."""
    voicing = score.voicing.strip().upper()
    if PLAIN_VOICING.match(voicing):
        score.soprano_parts, score.alto_parts, score.tenor_parts, score.bass_parts = (
            voicing.count(letter) for letter in "SATB"
        )


@dataclass
class CheckedFile:
    """What a file holds once every row is checked: the scores ready to
    save (not saved yet), the rows skipped and why, the headers that
    weren't recognised, and whether it was read as older Excel's encoding."""

    scores: list = dataclass_field(default_factory=list)
    skipped: list = dataclass_field(default_factory=list)
    ignored_columns: list = dataclass_field(default_factory=list)
    read_as_windows_1252: bool = False


def reason(form):
    """Why a row was skipped, in the spreadsheet's own words: "no title",
    or the column and what's wrong with it."""
    headers = {field: header for header, field, _ in COLUMNS}
    parts = []
    for name, errors in form.errors.items():
        header = headers.get(name, "")
        for error in errors.as_data():
            if error.code == "required":
                parts.append(f"no {header.lower()}")
            else:
                parts.append(f"{header}: {error.messages[0]}" if header else error.messages[0])
    return "; ".join(parts)


def check_file(data, organisation):
    """Read the file and check every row, for one church's library."""
    rows, fallback, ignored = read_rows(data)
    checked = CheckedFile(ignored_columns=ignored, read_as_windows_1252=fallback)
    for number, values in rows:
        form = ScoreImportRowForm(data=values, instance=Score(organisation=organisation))
        if form.is_valid():
            parts_from_voicing(form.instance)
            checked.scores.append(form.instance)
        else:
            checked.skipped.append((number, reason(form)))
    return checked
