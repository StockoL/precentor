# Calendar export

Four one-off scripts that turn published calendars, and the chants of
both forms of the Mass, into the data files Precentor loads. They aren't part
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
- `export_graduale_1974.py`: the names of the Ordinary Form's proper
  chants for Sundays and the major feasts, as the Graduale Romanum
  (1974) assigns them, from a six-page table of them.

I'm grateful to the calendar and chant projects' authors;
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
  Lent and its Alleluias for Eastertide, marked with that season. A
  day with several chants of one part numbers them from the second on,
  with `position`, in the order sung.

The script follows Divinum Officium's own references: a part that
names another day or a Common, a file that starts by naming the file
it builds on, a "vide C4a" rule in the Mass file or the saint's
Office file, and a weekday that sings the Sunday's Mass (but not Holy
Week's reformed days, such as `Quad6-5r`, which aren't weekdays of
Palm Sunday). A Tract is marked "!Tractus", sometimes with its psalm
verses after it, and a Sequence the day's rule asks for, such as All
Souls' Dies irae, is looked for in the Common the day is taken from.

On the Ember days and a few Lenten Wednesdays, the Mass has extra
readings before the Epistle, each with its own Gradual (an Alleluia in
Pentecost week), and on the Saturdays the Benedictus es after the
reading from Daniel, which is offered as a Canticle. These are read in
order. Divinum Officium marks the chant after the last reading only as
the Graduale, so `AFTER_LAST_READING` names the six days where it's a
Tract or an Alleluia.

Ash Wednesday, Candlemas and Holy Week have antiphons, responsories,
hymns and canticles outside the Mass, which Divinum Officium writes out
as prose with rubrics. `CEREMONIES` lists them by hand, in the order
sung, from the file each is read in, and the script stops if a
chant's opening isn't found at the start of a line of that file, so
nothing is typed from memory. I checked the list and chose the kinds:
on Good Friday "Eripe me" is a Responsory, and Sicut cervus is a
Canticle. Lauds after the Vigil is left out, as are the Vigil of
Pentecost's prophecies, which the 1955 reform removed.

Twenty-three days get no chants: twelve commemorations, which have no Mass of
their own, a weekday in the Christmas octave that borrows another, St
Zephyrinus, whose Common `C2-1b` isn't in the files, and the nine
England and Wales days, which Divinum Officium doesn't have.

`export_graduale_1974.py`, into `ordo/data/graduale_1974/`:

- `propers_current.json`: each Sunday's and major feast's Introit,
  Gradual, Alleluia, Tract, Sequence, Offertory and Communion, keyed
  like the occasions in `ordo/data/romcal/`, with the year of the
  Sunday cycle where the Graduale gives one ("A: Tolle puerum"), or
  where a Lent Sunday's chant goes with a Gospel read in one year.

The table is a PDF, so the script reads each piece of text with its
position: the columns sit at fixed distances from the left edge, and
read as plain text a year's alternative loses its column. `DAYS`
pairs every row's name with an occasion's key, and the script stops if
a row's name doesn't match the next one, so a misread can't pass. In
Eastertide the first of two Alleluias is put where the Gradual goes, as
for 1962. The table's antiphons, responsories, hymns and canticles, on
Palm Sunday, Holy Week, Ash Wednesday and the Presentation, are kept as
those parts, each in order, and a list of them ("Hosanna filio David;
Pueri Hebraeorum, portantes") is split into one chant each. Good Friday
and the Easter Vigil are keyed to the calendar's own days for them.
`REPARTED` moves three chants the table files under another part: the
Vigil's first two chants after the readings are Tracts, not canticles,
and Maundy Thursday's Pange lingua is the procession's hymn.
`ADDITIONS` lists chants the
table hasn't got, given from the Graduale itself: Year B's Communion
on the fifth Sunday of Lent, and the Vigil and Dawn Masses of
Christmas. 78 days and Masses are covered, with 494 chants.

I checked every row by eye against the PDF, and the days both forms
keep against the 1962 chants: 113 agree, and the 37 that differ are
either the same chant named more briefly or a day whose Mass changed in
1970 (the Holy Family, 1 January, the Second Sunday of Lent and others).

## Changes to the source data

romcal: only in names. The first letter is capitalised ("Fifth Sunday
in Ordinary Time"); the week is capitalised, as in the English Missal
("Saturday of the Second Week of Lent"); and one typo is corrected, in
`NAME_CORRECTIONS` ("All Souls' Day"). romcal has one Christmas, which
is the Mass during the Day and named so; `CHRISTMAS_MASSES` adds the
Vigil Mass and the Masses during the Night and at Dawn, each with its
own propers, with no precedence so they're listed with the day's
celebration and never in its place.

Missalemeum: none. Its names are used as they are.

The Graduale's table: names are kept as it prints them, without a
psalm verse after "...", an alternative after "vel.", or a note such
as "ad lib". `FIXES` corrects five rows its layout alone can't settle,
each with a note: two alternatives set outside their column, one set
on the next line, a Sequence marked on Trinity Sunday, which has none,
and the misprint "Sancticavit".

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

The Graduale's table, with pypdf in an environment of its own:

```
python -m venv graduale-env
graduale-env/Scripts/pip install pypdf
graduale-env/Scripts/python -I export_graduale_1974.py PATH/TO/propers1974.pdf
```

The PDF is at
https://media.churchmusicassociation.org/publications/pdf/propers1974.pdf.

The romcal versions are pinned in `package.json`. For Missalemeum I
used commit `75adfbb` (16 October 2026), and for Divinum Officium
commit `db57fc0` (30 October 2026). Then load the files
into the database from the project root:

```
python manage.py load_calendar
```
