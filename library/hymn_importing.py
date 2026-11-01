"""
Importing a hymnal's list from a spreadsheet: one hymn per row, by its
number in the book, with its first line, metre and tune if known. The file
is read by the score import's reader (importing.read_rows), so both share
the encodings, separators, header matching and limits.

A number new to the book is added, with a hymn of its own. For a number
the book already has, a detail is only added where the church has left
it blank; nothing it has written is overwritten. Everything the import
changes is recorded on the HymnImport, so it can be removed as a whole.
"""

from dataclasses import dataclass
from dataclasses import field as dataclass_field

from django import forms
from django.db import transaction

from .importing import read_rows
from .metre import normalise as normalise_metre
from .models import Hymn, HymnEntry, HymnImport, Tune

HYMN_COLUMNS = [
    ("Number", "number", True),
    ("First line", "first_line", False),
    ("Metre", "metre", False),
    ("Tune", "tune", False),
]

# Made-up rows for the page's example, as no hymnal's contents are copied.
HYMN_EXAMPLE = [
    ["1", "The opening words of the first verse", "88 88", "The tune's name"],
    ["2", "", "LM", ""],
    ["12a", "", "", ""],
]


class HymnRowForm(forms.Form):
    """One row, with the same limits as the hymn and tune fields."""

    number = forms.CharField(max_length=10)
    first_line = forms.CharField(max_length=200, required=False)
    metre = forms.CharField(max_length=40, required=False)
    tune = forms.CharField(max_length=100, required=False)


@dataclass
class CheckedHymns:
    rows: list = dataclass_field(default_factory=list)  # (row number, cleaned values)
    skipped: list = dataclass_field(default_factory=list)  # (row number, why)
    ignored_columns: list = dataclass_field(default_factory=list)
    read_as_windows_1252: bool = False


def why_skipped(form):
    headers = {field: header for header, field, _ in HYMN_COLUMNS}
    return "; ".join(
        f"no {headers[name].lower()}" if error.code == "required" else f"{headers[name]}: {error.messages[0]}"
        for name, errors in form.errors.items()
        for error in errors.as_data()
    )


def check_hymn_file(data):
    """Read the file and check every row. A number given twice is only
    taken the first time."""
    rows, fallback, ignored = read_rows(data, columns=HYMN_COLUMNS, noun="hymns")
    checked = CheckedHymns(ignored_columns=ignored, read_as_windows_1252=fallback)
    seen = set()
    for number, values in rows:
        form = HymnRowForm(data=values)
        if not form.is_valid():
            checked.skipped.append((number, why_skipped(form)))
        elif form.cleaned_data["number"].casefold() in seen:
            checked.skipped.append((number, f"number {form.cleaned_data['number']} is earlier in the file"))
        else:
            seen.add(form.cleaned_data["number"].casefold())
            checked.rows.append((number, form.cleaned_data))
    return checked


@transaction.atomic
def save_hymn_import(checked, hymnal, user, filename):
    """
    Apply a checked file to one hymnal as a pending import, all or nothing.
    Returns the import, or None if the file changed nothing because the
    book already had every number and detail in it.
    """
    church = hymnal.organisation_id
    batch = HymnImport.objects.create(
        organisation_id=church, hymnal=hymnal, created_by=user, original_filename=filename[:255]
    )
    entries = {entry.number.casefold(): entry for entry in hymnal.entries.select_related("hymn")}
    tunes = {tune.name.casefold(): tune for tune in Tune.objects.for_organisation(church)}
    filled, added_tunes, added, gained = [], [], 0, 0

    for _, values in checked.rows:
        details = {"first_line": values["first_line"], "metre": normalise_metre(values["metre"])}
        tune = None
        if values["tune"]:
            tune = tunes.get(values["tune"].casefold())
            if tune is None:
                tune = Tune.objects.create(organisation_id=church, name=values["tune"], metre=details["metre"])
                tunes[tune.name.casefold()] = tune
                added_tunes.append(tune.pk)
        entry = entries.get(values["number"].casefold())
        if entry is None:
            hymn = Hymn.objects.create(organisation_id=church, **details)
            HymnEntry.objects.create(
                organisation_id=church, hymn=hymn, hymnal=hymnal, number=values["number"],
                tune=tune, import_batch=batch,
            )
            added += 1
            continue
        # A number the book has: only blanks are filled, and each is noted.
        changed = False
        for field, value in details.items():
            if value and not getattr(entry.hymn, field):
                setattr(entry.hymn, field, value)
                filled.append(["Hymn", entry.hymn.pk, field, value])
                changed = True
        if changed:
            entry.hymn.save()
        if tune and entry.tune_id is None:
            entry.tune = tune
            entry.save(update_fields=["tune"])
            filled.append(["HymnEntry", entry.pk, "tune_id", tune.pk])
            changed = True
        gained += changed

    if not (added or gained or added_tunes):
        batch.delete()
        return None
    batch.report = {
        "added": added,
        "filled": gained,
        "unchanged": len(checked.rows) - added - gained,
        "tunes_added": len(added_tunes),
        "skipped": [[number, why] for number, why in checked.skipped],
        "ignored_columns": checked.ignored_columns,
        "read_as_windows_1252": checked.read_as_windows_1252,
    }
    batch.changes = {"filled": filled, "tunes": added_tunes}
    batch.save(update_fields=["report", "changes"])
    return batch
