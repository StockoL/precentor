"""
Importing a library from a spreadsheet saved as CSV, in Precentor's own
format: one score per row, under the headers in COLUMNS. Nothing here
touches a request or a page, so it can be tested with plain strings.

This part reads the file: it decodes it, works out the separator and
matches the headers. A file that can't work at all, such as one missing a
required column, stops with ImportProblem before any row is looked at.
"""

import csv
import io

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
