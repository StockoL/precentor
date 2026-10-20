# Calendar export

Two one-off scripts that turn published calendars into the data files
Precentor loads. They aren't part of the app: nothing here is
installed on the server, and the app never runs Node or imports either
library.

- `export_romcal.js`: the Ordinary Form, from
  [romcal](https://github.com/romcal/romcal) (copyright 2018 Julian
  Pereira, MIT licence).
- `export_missalemeum.py`: the 1962 calendar, from
  [Missalemeum](https://github.com/mmolenda/Missalemeum) (copyright
  2022 Marcin Molenda, MIT licence).

I'm grateful to both projects' authors;
[`docs/acknowledgements.md`](../../docs/acknowledgements.md) says
exactly how I've used each.

## What they write

`export_romcal.js`, into `ordo/data/romcal/`:

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

`export_missalemeum.py`, into `ordo/data/missalemeum/`:

- `general_1962.json`: every day of the 1962 calendar, all four
  classes, with Missalemeum's English names. Each key is Missalemeum's
  ID without its class and colour (`sancti:12-08`), which become
  fields.
- `blocks_1962.json`: the order of the Proper of Time, which
  `ordo/calendar_1962.py` lays out each year.
- `reference/general_1962.json`: Missalemeum's resolved calendar for
  2020 to 2040, first to third class, for the tests.

## Changes to the source data

romcal: only in names. The first letter is capitalised ("Fifth Sunday
in Ordinary Time"); the week is capitalised, as in the English Missal
("Saturday of the Second Week of Lent"); and one typo is corrected, in
`NAME_CORRECTIONS` ("All Souls' Day").

Missalemeum: none. Its names are used as they are.

## Running them again

romcal, with Node installed, from this folder:

```
npm install
node export_romcal.js
```

Missalemeum, with a copy of its repository and a Python environment of
its own (not the project's), from this folder:

```
python -m venv missalemeum-env
missalemeum-env/Scripts/pip install python-dateutil PyYAML trans mistune
missalemeum-env/Scripts/python -I export_missalemeum.py PATH/TO/Missalemeum/backend
```

The romcal versions are pinned in `package.json`. For Missalemeum I
used commit `75adfbb` (16 October 2026). Then load the files
into the database from the project root:

```
python manage.py load_calendar
```
