# Calendar export

A one-off script that turns [romcal](https://github.com/romcal/romcal)'s
Ordinary Form calendars into the data files Precentor loads. It isn't
part of the app: nothing here is installed on the server, and the app
never runs Node.

romcal is copyright 2018 Julian Pereira, MIT licence. I'm grateful to
its authors; [`docs/acknowledgements.md`](../../docs/acknowledgements.md)
says exactly how I've used it.

## What it writes

Into `ordo/data/romcal/`:

- `general_roman.json`, `england.json`, `wales.json`: each calendar's
  occasions (name, rank, precedence, date rule, transfers, colour and
  season). The general file holds every day in scope; a national file
  holds only the days that country, or Europe, which England and Wales
  belong to in romcal, adds or changes.
- `reference/<calendar>.json`: romcal's resolved calendar for every day
  from 2020 to 2040, which `ordo/test_reference.py` compares
  Precentor's against.

Ordinary weekdays and optional memorials are left out (see
[`docs/calendar_plan.md`](../../docs/calendar_plan.md), section 5),
except where a national calendar makes a general memorial optional:
that row is kept so it can override the general one.

## Changes to romcal's data

Only in names, and only these:

- the first letter is capitalised ("Fifth Sunday in Ordinary Time");
- the week is capitalised, as in the English Missal ("Saturday of the
  Second Week of Lent");
- one typo is corrected, in `NAME_CORRECTIONS` ("All Souls' Day").

## Running it again

With Node installed, from this folder:

```
npm install
node export_romcal.js
```

The versions in `package.json` are pinned, so the output only changes
when I change them. Then load the files into the database from the
project root:

```
python manage.py load_calendar
```
