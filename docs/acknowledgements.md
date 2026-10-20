# Precentor: Acknowledgements

Precentor stands on other people's work in several places: a calendar
library whose date rules I ported, published liturgical sources, a
design methodology and its layout ideas, two typefaces, and the
open-source packages it runs on. I'm grateful to everyone who made
these and shared them, often for nothing in return. This document
thanks each of them and says exactly what I took from their work,
where it is in the repository, and under what licence. Where I did
something differently from a source, I say so and why.

Sources marked **planned** are part of the calendar work still in
progress (Phase 6 of [`overhaul_plan.md`](overhaul_plan.md)); I'll
update their entries as each is used.

## The liturgical calendar (`ordo`)

### romcal

[romcal](https://github.com/romcal/romcal) is a JavaScript library that
generates the calendars of the Roman Rite. Copyright 2018 Julian
Pereira, MIT licence. I used the core package and its General Roman,
England and Wales calendar packages, version `3.0.0-dev.140`.

romcal saved me more work than anything else in this project. Its
authors have done the slow, careful job of turning the Church's
calendar rules into code and data for dozens of countries, and I'm
very grateful to Julian Pereira and everyone who has contributed to it.

How I used it:

- **The date rules.** [`ordo/dates.py`](../ordo/dates.py) is a Python
  port of romcal's date functions (`src/utils/dates.ts`, which I read
  from the source map published with the package). It covers the 34
  rules the Ordinary Form days in Precentor's scope need, such as the
  first Sunday of Advent, the Baptism of the Lord and the numbering of
  the weeks of Ordinary Time. The rule names are romcal's, converted to
  snake case, so romcal's data can be imported without a hand-kept
  mapping. I kept one of its quirks on purpose so the results match:
  a week of Ordinary Time that has days both before Lent and after
  Pentecost keeps only the later days.
- **Transfers.** `apply_transfers()` follows romcal's rules for moving
  a day (off a Sunday, out of Holy Week), with one difference. When a
  rule says "move to the day after Divine Mercy Sunday", romcal counts
  that day from the original date, so in 2022 St George lands on
  Divine Mercy Sunday itself. Precentor counts it from Divine Mercy
  Sunday, as the rule intends.
- **National settings.** Which feasts move to a Sunday in England and
  Wales (Corpus Christi, and Epiphany when 6 January is a Saturday or a
  Monday) come from romcal's calendar settings for those countries.
- **Precedence.** [`ordo/calendar.py`](../ordo/calendar.py) follows
  romcal's way of deciding which celebration a day keeps (its
  `generateCalendar`), with three changes: an impeded solemnity moves
  instead of being dropped, a memorial is never kept in Holy Week, and
  a day that may share with another memorial isn't sorted above
  higher-ranking days.
- **Checking.** I compared Precentor's dates with romcal's for every
  day in scope, in all three calendars, from 2020 to 2040: 14,448
  dates. Eight differed, all because of the transfer difference above.
  I then compared the whole resolved calendars for the same years;
  every difference is one of the cases listed in
  [`calendar_plan.md`](calendar_plan.md), section 4.
- **The calendar data.** A one-off export script,
  [`tools/calendar_export/export_romcal.js`](../tools/calendar_export/export_romcal.js),
  takes each day's name, rank, precedence, date rule, transfers,
  colour and season from romcal's definitions (version
  `3.0.0-dev.140`, British English names) into the JSON files in
  `ordo/data/romcal/`, which `manage.py load_calendar` loads. The only
  changes I made are to names: capitalisation, and one typo. romcal
  isn't installed in the project and nothing depends on it at runtime.
- **The reference calendars.** The same script saves romcal's resolved
  calendars for 2020 to 2040 in `ordo/data/romcal/reference/`, and
  [`ordo/test_reference.py`](../ordo/test_reference.py) checks
  Precentor against them on every test run.

romcal's licence notice is in
[`ordo/ROMCAL_LICENSE.txt`](../ordo/ROMCAL_LICENSE.txt), beside the
code ported from it.

### General Norms for the Liturgical Year and the Calendar

The Church's own rules for the Ordinary Form calendar (1969). The
Table of Liturgical Days in its no. 59 orders every kind of day from
the Paschal Triduum down to ordinary weekdays, and decides which
celebration is kept when two fall on the same date. Its levels are
the `precedence` choices on `LiturgicalOccasion`; the labels are my own
short summaries. The precedence rules in
[`ordo/calendar.py`](../ordo/calendar.py) follow its nos. 59 to 61:
which day wins, and that an impeded solemnity moves to the nearest day
not taken by a day of levels 1 to 8.

### General Instruction of the Roman Missal, and a notification of 2018

Two more Church documents settle details of the precedence rules. The
General Instruction of the Roman Missal, no. 355, says when an
obligatory memorial may still be kept on a privileged weekday, and
that none is kept in Holy Week. The Congregation for Divine Worship's
2018 notification on the memorial of Mary, Mother of the Church, says
that memorial prevails over another memorial on the same day.

### Missalemeum

[Missalemeum](https://github.com/mmolenda/Missalemeum) is a Python
application for the 1962 Missal. Copyright 2022 Marcin Molenda, MIT
licence. I used its repository at commit `75adfbb`. Working out the
1962 calendar's precedence is intricate, and Missalemeum's careful,
well-commented rules made the port possible; my thanks to Marcin
Molenda for making it open source.

How I used it:

- **The calendar rules.** [`ordo/calendar_1962.py`](../ordo/calendar_1962.py)
  is a port of its calendar factory and rules (`api/kalendar/factory.py`
  and `rules.py`) and of its Table of Precedence, in its order. The
  rules test a day's class and kind as fields instead of matching
  patterns against IDs; the reasons, and the two days where the results
  differ, are in [`calendar_plan.md`](calendar_plan.md), section 4.
- **The calendar data.** A one-off script,
  [`tools/calendar_export/export_missalemeum.py`](../tools/calendar_export/export_missalemeum.py),
  takes every day's English name, class and colour, and the blocks of
  the Proper of Time, into `ordo/data/missalemeum/`, which
  `manage.py load_calendar` loads. I made no changes to its data.
- **Checking.** The same script saves Missalemeum's resolved calendars
  for 2020 to 2040, and `ordo/test_reference.py` checks Precentor
  against them on every test run.

Missalemeum's licence notice is in
[`ordo/MISSALEMEUM_LICENSE.txt`](../ordo/MISSALEMEUM_LICENSE.txt), beside
the code ported from it.

### The Ordo 2025-2026, Latin Mass Society (planned)

[The Ordo 2025-2026](https://lms.org.uk/sites/default/files/u5374/final_ordo_1.42_2025-2026.pdf),
compiled by Peter Day-Milne, copyright The Latin Mass Society 2025.
It gives the rank of each day of the 1962 calendar separately for the
dioceses of England and of Wales. **Planned:** I'll take facts only
from it (which feasts England and Wales add or rank differently, on
which dates, of which class and colour) and never its wording. I'll
also check the 2025-26 year against it. I'm grateful to the Latin
Mass Society for publishing it freely, and to Peter Day-Milne for the
work of compiling it each year.

### The date of Easter

[`ordo/utils.py`](../ordo/utils.py) calculates Easter Sunday with the
Anonymous Gregorian algorithm, published by Jean Meeus in
*Astronomical Algorithms* after earlier versions by Jones and Butcher.

## Design and front end

### CUBE CSS

The way the stylesheets are organised (global styles, compositions,
blocks and utilities, in that order of specificity) follows Andy
Bell's [CUBE CSS](https://cube.fyi) methodology. The reasoning is in
[`design_system.md`](design_system.md). Andy Bell's writing on CSS has
shaped how I write stylesheets, and I'm thankful he shares so much of
it.

### Every Layout

Most of the layout compositions in `static/src/compositions/` (center,
cluster, flow, grid, reel, sidebar, switcher and wrapper) come from
looseleaf-ui, an earlier toolkit of my own. Its layouts were based on
the primitives described in [Every Layout](https://every-layout.dev)
by Heydon Pickering and Andy Bell. I added the cover composition
during this project, following Every Layout's Cover. The flow composition spaces
siblings with Heydon Pickering's "lobotomised owl" selector
(`* + *`). Every Layout taught me to think of layout as a small set of
reusable parts, and I owe both authors thanks for that.

### The CSS reset

[`static/src/global/reset.css`](../static/src/global/reset.css) is
adapted from Andy Bell's
["A (more) Modern CSS Reset"](https://piccalil.li/blog/a-more-modern-css-reset/),
wrapped in the `reset` cascade layer.

### Utopia

The fluid type and space scales were generated with
[Utopia](https://utopia.fyi), by James Gilyead and Trys Mudford. The
settings I chose are in [`design_system.md`](design_system.md). Thank
you to both for a tool that makes fluid sizing simple to get right.

### Font fallback metrics

[`build-font-fallback.js`](../build-font-fallback.js) reimplements the
formula Next.js uses to size a fallback font to match a web font
(`calculateSizeAdjustValues` in its `font-utils.ts`; Next.js is
copyright Vercel, MIT licence). The script is my own; the formula is
theirs.

### Colour contrast

I checked colour pairs with the contrast ratio formula from the W3C's
[Web Content Accessibility Guidelines](https://www.w3.org/TR/WCAG22/).

## Typefaces

Both are self-hosted, with their licence files beside them in
`static/src/global/fonts/`. My thanks to their designers, Georg
Duffner and Octavio Pardo for EB Garamond and Rasmus Andersson for
Inter, and to everyone who has contributed to them, for releasing such
fine typefaces under an open licence.

| Typeface | Copyright | Licence |
| --- | --- | --- |
| [EB Garamond](https://github.com/octaviopardo/EBGaramond12) | 2017 The EB Garamond Project Authors | SIL Open Font License 1.1 |
| [Inter](https://github.com/rsms/inter) | 2020 The Inter Project Authors | SIL Open Font License 1.1 |

## Software Precentor runs on

Precentor is small next to the software underneath it, and I'm
grateful to the maintainers of each of these packages.

| Package | Licence | Used for |
| --- | --- | --- |
| [Django](https://www.djangoproject.com) | BSD-3-Clause | The web framework |
| [Pillow](https://python-pillow.org) | MIT-CMU | Checking and cropping the crest image |
| [WhiteNoise](https://whitenoise.readthedocs.io) | MIT | Serving static files |
| [Gunicorn](https://gunicorn.org) | MIT | The web server on Heroku |
| [psycopg2](https://www.psycopg.org) | LGPL with exceptions | Connecting to PostgreSQL |
| [dj-database-url](https://github.com/jazzband/dj-database-url) | BSD-3-Clause | Reading the database address from the environment |
| [python-dotenv](https://github.com/theskumar/python-dotenv) | BSD-3-Clause | Loading settings from `.env` in development |
| [Playwright](https://playwright.dev/python/) | Apache-2.0 | Browser tests (development only) |

Django brings in asgiref and sqlparse (both BSD), tzdata (Apache-2.0)
and packaging (Apache-2.0 or BSD-2-Clause).
