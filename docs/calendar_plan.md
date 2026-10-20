# Precentor: Calendar Data and Precedence

A design document for Phase 6, item 1 of [`overhaul_plan.md`](overhaul_plan.md):
filling `ordo` with the real calendars, and teaching it which
celebration wins when two fall on the same day. I've written it before
any code, because the decisions here shape the model, the data and
the tests.

## 1. What I decided before writing this (20 Oct 2026)

- **Both forms of the Roman Rite:** the Ordinary Form and the 1962
  Extraordinary Form, as `calendar_use` already allows.
- **Obligatory memorials included,** as well as Sundays, solemnities
  and feasts. Optional memorials are left out: a choir is very unlikely to
  sing for one, so they're future development.
- **Precedence worked out by Precentor itself:** each occasion stores
  its rank and a date rule, and Precentor applies the tables of
  precedence for any year. Published libraries supply the seed data
  and serve as test references, but nothing at runtime depends on
  them.
- **The national calendar is the user's choice:** the General Roman
  Calendar, England or Wales to begin with, with room for the United
  States and others later.

## 2. Sources

How each source has actually been used, and its licence, is recorded
as the work goes in [`acknowledgements.md`](acknowledgements.md).

| Form | Source | Licence | Used for |
| --- | --- | --- | --- |
| Ordinary Form | [romcal](https://github.com/romcal/romcal) 3 (core and calendar packages, version `3.0.0-dev.140`) | MIT | Definitions (names, ranks, date rules, transfer rules, colours, seasons) and a reference calendar for each year |
| 1962 | [Missalemeum](https://github.com/mmolenda/Missalemeum) | MIT | Names, classes and colours, and a reference calendar for each year |
| 1962, England and Wales | [The Ordo 2025-2026](https://lms.org.uk/sites/default/files/u5374/final_ordo_1.42_2025-2026.pdf), Latin Mass Society | Copyright; facts only | Which feasts England and Wales add or rank differently, and a reference for the 2025-26 year |

romcal splits England and Wales into two calendars. They differ in
places such as St David, a solemnity in Wales. So the choices are
General Roman, England and Wales, and each national calendar is
romcal's own list of additions and overrides on top of the general
one (England has 46, Wales 25, the United States 26).

What I checked against romcal's England data, and not my own
memory: since the bishops' 2016 decision, Epiphany and the Ascension
stay on 6 January and the Thursday. Corpus Christi moves to the
Sunday, and so does SS Peter and Paul when 29 June is a Saturday or a
Monday (in 2026 it's kept on Sunday 28 June). St George is a
solemnity in England and an optional memorial in the general
calendar.

Missalemeum has no supplement for England (its local calendar is
Polish). For that I'm using the Latin Mass Society's annual Ordo, which
gives the rank of each day separately for the dioceses of England and
of Wales. On 23 April, for example, St George is a feast of the first
class in England and of the third class in Wales; and St Thomas of
Canterbury, on 29 December, is first class in both. The Ordo is
copyright, so I take only facts from it (which days, on which dates,
of which class and colour) and never its wording. Feasts proper to a
single diocese or church, which the Ordo also lists, are out of scope.

## 3. The model

`LiturgicalOccasion` gains:

- **`key`:** a stable identifier from the source (`george_of_lydda_martyr`).
  A national calendar overrides a general day by using the same key.
- **`calendar`:** which calendar the row belongs to (`general_roman`,
  `england`, `wales`; later `united_states`). Together with
  `calendar_use` and `key` it's unique.
- **`rank`:** for the Ordinary Form, solemnity, Sunday, feast,
  memorial or weekday; for 1962, class I to IV.
- **`precedence`:** the row's place in the Table of Liturgical Days
  (Ordinary Form, levels 1 to 13 with lettered sub-levels such as 4a
  and 8c) or the 1962 table, stored as a number that sorts correctly
  plus its code for display.
- **`date_rule`, `date_rule_args` and `date_offset_days`:** either a
  fixed month and day (as now), or a named rule with its arguments and
  a number of days to add. The 5th Sunday of Ordinary Time is
  `date_of_ordinary_time` with `[0, 5]`, and the Thursday after Ash
  Wednesday is `ash_wednesday` plus one day. The rules live in
  `ordo/dates.py`, and their names are romcal's in snake case, so its
  data converts without a hand-kept mapping. The days in scope use 34
  rules; most are a line from Easter, Christmas or the first Sunday of
  Advent, and the longest is the numbering of Ordinary Time. The
  existing `easter_offset_days` stays for occasions entered by hand.
- **`transfers`:** the moves a day makes in particular years, stored as
  JSON. romcal uses only four shapes: "if it falls on a Sunday, move
  it a day later", "if it falls on a Saturday, move it a day earlier",
  "if it falls between Palm Sunday and Divine Mercy Sunday, move it to
  the Monday after" and "... move it to the Saturday before". A JSON
  field keeps those four shapes in one column that both SQLite and
  Postgres support, without a table for something this small.

`SiteConfig` gains **`national_calendar`**, chosen on Settings by a
conductor. I put it on `SiteConfig` because the calendar belongs to the
church, the same as its name and crest, and one church follows one
national calendar. A term or service doesn't need its own.

`COLOUR_CHOICES` gains **black**: 1962 uses it on Good Friday and at
Requiem Masses. It needs a `liturgical-black` token in both themes.

## 4. The engine

A new module, `ordo/calendar.py`, works out a whole year at a time:

1. Take the general calendar's occasions for the chosen form, and
   replace or add the national calendar's rows by key.
2. Give each occasion its date for the year from its `date_rule`, then
   apply its `transfers`.
3. Group the occasions by date and sort each day by precedence.
4. Apply the rules of the form:
   - **Ordinary Form** (the General Norms for the Liturgical Year,
     nos. 59 to 61): the highest celebration wins. A solemnity that's
     impeded moves to the nearest free day; a feast or memorial that's
     impeded is left out that year; a Sunday in Ordinary Time gives
     way to a feast of the Lord or a solemnity, but a Sunday of
     Advent, Lent or Easter gives way to nothing. Built: see "The
     Ordinary Form engine, as built" below.
   - **1962** (the rubrics of the 1960 Code): classes I to IV, where a
     Sunday of the first class beats any feast, a Sunday of the second
     class gives way only to feasts of the first class and feasts of
     the Lord, and a defeated feast is often commemorated. Ported
     from Missalemeum's rules, keeping only what decides the day's
     name: no propers, prefaces or Office. Built: see "The 1962
     engine, as built" below.
5. Return each date's celebration first, then anything still observed
   alongside it (a commemoration in 1962, a memorial that becomes a
   commemoration in Lent).

`occasion_for_date()` keeps its name and returns the same kind of
list, now in that order. The service form already offers the first
match as the occasion and the rest as additional occasions, so the
suggestion becomes "this is the day, and this is also kept".

### The Ordinary Form engine, as built

`ordo/calendar.py` sorts each day by the Table of Liturgical Days: by
level, then by the letter within it, then the Proper of Time ahead of
a saint's day of the same rank (the Sacred Heart ahead of St John the
Baptist in 2022). The first is the day's celebration. Kept alongside
it:

- on a privileged weekday (Lent, 17 to 24 December, the Christmas
  Octave), any obligatory memorial, which becomes optional;
- on a memorial that shares (only the Immaculate Heart of Mary),
  another memorial; otherwise the first of two memorials prevails, as
  Mary, Mother of the Church does by the 2018 notification on it;
- on the first day of the Triduum, Thursday of Holy Week, since the
  day is Lent until the evening Mass of the Lord's Supper;
- nothing in Holy Week, where no memorial is kept (GIRM 355a). I check
  this by date, because romcal's data ranks Monday to Wednesday of
  Holy Week as privileged weekdays.

A solemnity that's impeded, and that has no transfer of its own in
the data, moves to the next day not taken by a day of levels 1 to 8.
Anything else impeded is left out for the year. Occasions entered by
hand have no precedence; they're listed after the resolved days, so
they always appear.

A lookup works out the whole year each time, in one query; at about
250 occasions this is quick, so there's no cache to go stale when an
occasion is edited.

**Checked against romcal.** I compared the engine with romcal's
resolved calendars for every day from 2020 to 2040, in all three
calendars: about 12,400 days. They differ on 91, in four ways. In the
first, the order is my choice; in the other three, Precentor follows
the norms and romcal doesn't:

| Difference | Days | Example |
| --- | --- | --- |
| romcal lists Holy Thursday's Lent weekday first; Precentor lists the Lord's Supper first, the Mass a choir sings | 63 | every year |
| romcal drops an impeded solemnity; Precentor moves it (General Norms, no. 60) | 13 | St George on Monday 24 April 2023; St David on 2 March 2026 in Wales; St John the Baptist on 25 June 2033 |
| romcal sorts a day that may share above everything, so a memorial beats a solemnity or feast | 7 | the Immaculate Heart over SS Peter and Paul on 29 June 2030 |
| romcal's transfer bug from step 2 | 8 | St Joseph on 17 March 2035; St George on Monday 25 April 2022 |

One known difference from what actually happened: in 2022 the
Nativity of St John the Baptist, impeded by the Sacred Heart, was
moved back to Thursday 23 June by a particular decision of the Holy
See. The general rule moves it forward, to 25 June, which is what
Precentor shows. A decision of that kind can't be derived from the
norms, so a conductor would pick the occasion by hand that year.

### The 1962 engine, as built

`ordo/calendar_1962.py` is a port of Missalemeum's calendar factory and
rules, which work differently from romcal's. The Proper of Time isn't a
formula per day but a set of blocks laid out each year: the Sundays
after Epiphany run until Septuagesima, and any it cuts short are
resumed in November before the last Sunday after Pentecost (in 2024,
after an early Easter, the Fifth and Sixth Sundays after Epiphany fell
on 10 and 17 November). The blocks are data, in
`ordo/data/missalemeum/blocks_1962.json`; the layout and the Proper of
Time's one date rule, `tempora_1962`, are code. The saints are added on
their dates, and the year is then gone through a day at a time,
applying Missalemeum's twenty-odd rules in its order: the Vigil of
Christmas on a Sunday, All Souls moving off a Sunday, two first-class
feasts (the lower moves to the first free day), a second-class Sunday
with a second-class feast (commemorated), Lent weekdays with saints,
and so on.

Two changes from Missalemeum:

- **Fields, not IDs.** Missalemeum's rules match patterns against IDs
  such as `sancti:12-08:1:w`, with the class and colour inside them.
  Precentor's rows have a key (`sancti:12-08`) and the class and colour
  as fields, so a national calendar can override a day by key, and the
  rules test the fields.
- **Fourth-class days aren't listed.** They take part in the rules, so
  commemorations come out right, but like optional memorials in the
  Ordinary Form they're left out of what Precentor shows. Missalemeum's
  rule for the Saturday Office of Our Lady is left out for the same
  reason: it only ever produces a fourth-class day.

**Checked against Missalemeum.** For every day from 2020 to 2040
(about 6,100 days with a listed celebration), Precentor and
Missalemeum agree on all but two: Palm Sunday 2030 and Laetare Sunday
2035, where Missalemeum also keeps a third-class saint. Both Sundays
have two colour letters in Missalemeum's IDs (red and violet, rose and
violet), which its "first class" pattern doesn't match, so the day
falls through to a rule meant for fourth-class days. Under the 1960
rubrics a third-class feast on a first-class Sunday is left out, as
Precentor shows. The first run of the comparison also found two keys I
had written from memory without their suffixes (`sancti:08-09t`, the
Vigil of St Lawrence, and `sancti:06-28r`, the Vigil of SS Peter and
Paul); the rules now take every key from Missalemeum's constants.

## 5. What goes in

| | Included | Left out for now |
| --- | --- | --- |
| Ordinary Form | Sundays, solemnities, feasts, obligatory memorials, and the privileged weekdays (Ash Wednesday, the weekdays of Lent, Holy Week, the Easter Octave, 17 to 24 December, the Christmas Octave) | Optional memorials and ordinary weekdays |
| 1962 | Days of the first, second and third class: Sundays, feasts, vigils, Ember Days, the weekdays of Advent and Lent, and the octaves of Christmas, Easter and Pentecost | Fourth-class days: ordinary ferias, commemorations and the Saturday Office of Our Lady |

The weekdays of Lent are in because of precedence, not because a
choir sings on them: without them, the engine would take a memorial
that falls in Lent for the day's celebration, when in Lent it's only
commemorated.

Third-class feasts are the nearest 1962 equivalent of obligatory
memorials. Optional memorials are future development (section 1); the
model doesn't need to change for them.

## 6. Getting the data in

Two small export scripts, kept in `tools/calendar_export/` with a
README crediting both sources:

- a Node script that reads romcal's definitions and writes one JSON
  file per calendar;
- a Python script that reads Missalemeum's tables and writes the 1962
  file.

The JSON files are committed in `ordo/data/`. Neither library is
installed in the project: a fresh clone, a test run and the Heroku
deploy need neither Node nor Missalemeum.

### As built (Ordinary Form)

`tools/calendar_export/export_romcal.js` writes `general_roman.json`,
`england.json` and `wales.json` into `ordo/data/romcal/`, with romcal's
resolved calendars for 2020 to 2040 beside them in `reference/` for the
tests. Its README lists the only changes made to romcal's data, all in
names: a capital first letter, a capital "Week" as in the English
Missal, and one typo.

Two things turned up in the data:

- England and Wales extend a Europe calendar in romcal, whose patrons
  (St Benedict, St Bridget, St Catherine of Siena and others) are
  feasts, so a national file takes every row that doesn't come from
  the general calendar, not only the country's own.
- England makes one general memorial optional (St Elizabeth of
  Hungary). Its row is kept, at precedence level 12, so it overrides
  the general one; the engine then leaves it out like any optional
  memorial.

**A command, not a data migration.** I planned a data migration, but
loading is a management command instead: `python manage.py
load_calendar` (`ordo/calendar_data.py`). A data migration runs once,
so every update to the data would need another migration; it would
also put about 260 occasions into every test database, under tests
that build small calendars of their own. The command can be run again
at any time: it matches each occasion by form, calendar and key,
creates or updates it, and never touches an occasion entered by hand
(which has no key). The cost is that a deploy has to run it after
`migrate`, which Phase 7 of [`overhaul_plan.md`](overhaul_plan.md) now
says.

## 7. Testing

- **Unit tests** for each date rule (the 5th Sunday of Ordinary Time,
  Christ the King, Baptism of the Lord when Epiphany falls on 7 or 8
  January, and so on) and each precedence rule, using years chosen
  for their clashes: St Joseph in Holy Week, the Immaculate Conception
  on an Advent Sunday, the Annunciation in the Easter Octave, All
  Souls on a Sunday.
- **Reference tests:** the export scripts also write, for every day
  from 2020 to 2040, the celebration romcal or Missalemeum gives for
  each calendar. A test runs Precentor's engine over the same days and
  compares, for the occasions in scope. Any disagreement is either a
  bug in my code or a case I'll document with the reason.
- **The 2025-26 Ordo as a check on England and Wales in 1962:** the
  class of each day's celebration in England and in Wales, taken from
  the Ordo, compared with the engine for that liturgical year.

## 8. Order of work

Each step ends with the tests passing and the changes left for me to
review and commit.

1. Model fields, the `national_calendar` setting and the black colour.
2. Ordinary Form date rules, with unit tests.
3. Ordinary Form precedence, with unit tests.
4. romcal export, data files and the data migration for General
   Roman, England and Wales, with reference tests.
5. 1962 date rules and precedence, with unit tests.
6. Missalemeum export, the England and Wales supplements from the
   Ordo, data and reference tests.
7. The service form's suggestions in precedence order, and the choice
   on Settings.
8. README and `models_plan.md`.

Adding the United States later is then one more run of the export
script and one more choice on Settings.

## 9. Questions settled (20 Oct 2026)

- **Optional memorials:** left out, as future development.
- **1962 in England and Wales:** taken from the Latin Mass Society's
  Ordo (section 2), not left universal.
