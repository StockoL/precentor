# Calendar export

Three one-off scripts that turn published calendars, and the 1962
Missal's chants, into the data files Precentor loads. They aren't part
of the app: nothing here is installed on the server, and the app never
runs Node or imports any of these projects.

- `export_romcal.js`: the Ordinary Form, from
  [romcal](https://github.com/romcal/romcal) (copyright 2018 Julian
  Pereira, MIT licence).
- `export_missalemeum.py`: the 1962 calendar, from
  [Missalemeum](https://github.com/mmolenda/Missalemeum) (copyright
  2022 Marcin Molenda, MIT licence).
- `export_divinum_officium.py`: the names of the 1962 Missal's proper
  chants, from
  [Divinum Officium](https://github.com/DivinumOfficium/divinum-officium)
  (MIT licence; the liturgical texts are in the public domain).

I'm grateful to all three projects' authors;
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

`export_divinum_officium.py`, into `ordo/data/divinum_officium/`:

- `propers_1962.json`: the opening words of each 1962 day's Introit,
  Gradual, Alleluia, Tract, Sequence, Offertory and Communion, keyed
  like the occasions in `general_1962.json`. Divinum Officium's file
  names are those keys, as Missalemeum is built on its files, so no
  matching by name is needed. A saint's day also has its Tract for
  Lent and its Alleluias for Eastertide, marked with that season.

The script follows Divinum Officium's own references: a part that
names another day or a Common, a file that starts by naming the file
it builds on, a "vide C4a" rule in the Mass file or the saint's
Office file, and a weekday that sings the Sunday's Mass. Twenty-three
days get no chants: twelve commemorations, which have no Mass of
their own, a weekday in the Christmas octave that borrows another, St
Zephyrinus, whose Common `C2-1b` isn't in the files, and the nine
England and Wales days, which Divinum Officium doesn't have.

## Changes to the source data

romcal: only in names. The first letter is capitalised ("Fifth Sunday
in Ordinary Time"); the week is capitalised, as in the English Missal
("Saturday of the Second Week of Lent"); and one typo is corrected, in
`NAME_CORRECTIONS` ("All Souls' Day").

Missalemeum: none. Its names are used as they are.

Divinum Officium: only the opening words are kept, never the full
texts. They stop at the first punctuation (or the next, after a single
word), at five words, and not on a small word such as "et"; and the
acute and grave accents the texts are printed with are removed, as the
Graduale's index has none ("Ad te levavi").

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

Divinum Officium is large, so a sparse copy of the four folders the
script reads is enough:

```
git clone --filter=blob:none --no-checkout https://github.com/DivinumOfficium/divinum-officium.git
cd divinum-officium
git sparse-checkout set --no-cone web/www/missa/Latin/Tempora/ web/www/missa/Latin/Sancti/ web/www/horas/Latin/Commune/ web/www/horas/Latin/Sancti/ /LICENSE
git checkout db57fc0
python -I PATH/TO/export_divinum_officium.py .
```

The romcal versions are pinned in `package.json`. For Missalemeum I
used commit `75adfbb` (16 October 2026), and for Divinum Officium
commit `db57fc0` (30 October 2026). Then load the files
into the database from the project root:

```
python manage.py load_calendar
```
