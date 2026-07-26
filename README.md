# Precentor

_A repertoire and service-planning tool for church musicians._

_Milestone 3 Project — Code Institute_

> **Status:** The full application is built: all four Django apps
> (`library`, `ordo`, `planning`, `comments`) are modelled, migrated,
> tested, and admin-registered; every view/template described below is
> implemented and permission-gated; and the visual design system
> (tokens, CUBE CSS Compositions/Blocks, self-hosted typography, the
> liturgical accent) is complete — see
> [`docs/design_system.md`](docs/design_system.md). This document
> retains its original concept/rationale framing throughout, since the
> reasoning below is what the implementation actually followed — where
> reality diverged from an early plan (e.g. `LiturgicalOccasion`'s
> `fixed_date` becoming `fixed_month`/`fixed_day`), that's called out
> explicitly in [`docs/models_plan.md`](docs/models_plan.md) rather
> than silently edited away. Remaining work: deployment and final
> documentation wrap-up (screenshots, install instructions).

A **precentor** is the traditional title for the person responsible for
directing a church's music — the role this tool is built around. Its
liturgical calendar engine is named **Ordo**, after the traditional
document/book setting out a church's calendar of observances for the
year — the same term used within this project for the feature that
tracks liturgical seasons and feast days.

---

## 1. The Problem

Choral conductors working in a church context (Anglican or Catholic, though
the pattern holds more widely) are responsible for planning music across a
term made up of multiple weekly services — typically a midweek service
and one or two Sunday services. This involves:

- Knowing what music is available, and whether it's currently _singable_
  by the choir (right voicing, right forces).
- Avoiding over-repetition, while still allowing deliberate repeats.
- Matching music to the liturgical calendar — some pieces are general,
  others are written for, or traditionally associated with, a specific
  season or feast day.
- Producing a clean, public-facing "music list" for the congregation —
  currently a manual, repetitive typing/formatting task every term.
- Coordinating with a librarian or music administrator who manages the
  physical copies, separately from the conductor's musical decisions.

None of this is well served by a spreadsheet, which can't easily encode
relationships (which piece was sung when, in what role, for which
service), and can't distinguish between "still deciding" and "deliberately
nothing planned here."

## 2. Who This Is For

This is a **single-tenant** tool: built for one church's choir/music
department, not a multi-church platform. (Benefices with several choirs
under one director are a real and interesting edge case, but explicitly
out of scope for this project.)

Two user roles, reflecting a genuine division of labour:

| Role                        | Owns                                                                         | Can see                                               |
| --------------------------- | ---------------------------------------------------------------------------- | ----------------------------------------------------- |
| **Conductor**               | Repertoire planning: proposing, confirming, un-confirming, marking roles N/A | Everything                                            |
| **Librarian / Music Admin** | Physical library data: copies owned, filing location, condition              | Repertoire (read-only), physical library (read/write) |

Both roles participate in a shared comment/query thread system (see §7).

## 3. Core Domain Concepts

### 3.1 Score

A piece of music in the library. Fields include title, composer/arranger,
voicing (SATB, SATTB, unison, etc.), **language**, publisher, filing
location, number of copies owned, and an optional **rehearsal lead-time
tag** (see §3.5). Scores can be tagged with liturgical seasons/occasions
they suit.

### 3.2 Term, Service, and Role Slots

A **Term** is simply a named container with a date range (e.g. "Lent
2027"). Any number of terms can be open at once — the app makes no
assumption about which one is "current"; a chronological list of all open
terms is the natural landing view for every user, and today's date makes
it obvious at a glance which term(s) matter right now. (An earlier idea
of an explicit "active term" flag was deliberately dropped — it would
have duplicated information the date already provides.)

A **Service** belongs to a Term, has a date, a type (Sung Eucharist,
Choral Evensong, etc.), and a liturgical occasion (see §3.4).

Each service type has a **default template** of musical **role slots** —
e.g. Sung Eucharist typically needs a _Setting_ and an _Anthem_; Choral
Evensong typically needs _Canticles_, _Responses_, and an _Anthem_. When
a service is created, it starts with a copy of its template's roles —
but from that point on, roles belong to the _instance_, not the
template. Roles can be added, removed, or marked **N/A** on a
service-by-service basis (a special day might need an extra anthem, or
have no setting at all, as on Good Friday).

Template editing itself is **out of scope for MVP** — a small, sensible
set of templates is seeded directly, and all flexibility lives at the
instance level. This is flagged as a natural "future development."

### 3.3 Proposing and Confirming

Each role slot holds a **shortlist of proposed pieces** (e.g. two anthem
options still being weighed up). Confirmation happens **per piece**, not
per role or per service — this allows realistic cases like two anthems
in one service, or a mixed setting. A confirmed piece can always be
**un-confirmed** again; nothing is a one-way door.

Marking a role **N/A** is itself treated as an active planning decision,
equivalent to confirming — it means "I've considered this and there's
deliberately nothing here," not "nothing has happened yet."

A service's overall status is **derived**, not stored directly:

- **Not started** — no candidates anywhere
- **In progress** — some roles still only have proposed (unconfirmed) pieces
- **Complete** — every role is either confirmed or marked N/A

This derived status is what powers the term-level "at a glance" view,
letting a conductor scan a term and instantly see which services still
need attention.

### 3.4 Ordo (the Liturgical Calendar)

**Ordo** is this project's name for its liturgical calendar engine.
Catholic and Church of England calendars follow the same broad shape
(Advent → Christmas → Epiphany → Lent → Easter → the season after
Pentecost/Trinity) but differ in naming, some boundaries, and many
saints'/feast days. Some occasions are fixed-date (Christmas Day),
others are moveable, calculated relative to Easter (Ash Wednesday, Palm
Sunday, Pentecost). Services carry a liturgical occasion drawn from
Ordo, which drives both automatic tagging/filtering of suitable Scores
and the seasonal colour context used in the UI.

### 3.5 Rehearsal Lead-Time (not "difficulty")

Rather than an inherently subjective "difficulty rating," Scores carry
an **optional rehearsal lead-time tag**, entirely at the conductor's
discretion — a signal of how far in advance a piece typically needs to
enter rehearsal planning, rather than a contested judgement of how hard
it "is." This makes the tag directly actionable for term planning rather
than just descriptive.

### 3.6 "Last Sung"

Derived from service history (the most recent service a Score was
confirmed for), shown at a glance as a single date. Clicking through
reveals the **complete history** of every occasion the piece has been
sung — useful for a librarian or conductor checking how often something
has been repeated over time. The same piece can validly serve multiple
roles or repeat across different services and terms.

## 4. The Public Music List

Modelled directly on a real example (a termly printed list from a parish
church), the tool can generate a formatted document from a term's
current state:

- **Snapshot, not live** — "print music list" captures the state _as of
  that moment_. If things change afterwards (as they sometimes do, right
  up to the day), the printed/shared version simply reflects what was
  true when it was generated — deliberately not something the app tries
  to keep in sync after the fact.
- **Latest version only** — the app doesn't archive every past
  generation. Once a list has been shared or printed, its lifecycle
  belongs to whoever received it; the app is only concerned with "now."
- **Partial generation is allowed** — a still-in-progress term can still
  produce a useful internal document. Unconfirmed/proposed roles render
  as a visible **blank**, clearly marked with a **"TBC" watermark**,
  removing any ambiguity about whether something is deliberately absent
  (N/A) or simply not yet decided. This distinction matters: a public
  document should never accidentally expose an undecided tentative
  choice as if it were settled.

## 5. Roles and Permissions, Revisited

The conductor/librarian split isn't just about visibility — it mirrors
a real division of labour: **the conductor decides, the librarian
fulfils.** The librarian has genuine ownership of the physical library
side (which the conductor generally doesn't touch), while repertoire
decisions (propose/confirm/un-confirm/N/A) remain the conductor's alone,
with the librarian able to see everything but change none of it.

## 6. Comment/Query Threads

A lightweight, deliberately bounded feature allowing the librarian and
conductor to discuss specific items without leaving the app:

- **Flat structure** — one layer of comments with replies appended
  underneath; no arbitrary nested threading.
- **Authored** — shown with the commenting user's initials.
- **Open/closed**, closeable by either party.
- **Three colour states**: open / open-with-replies / closed.
- **Targets**: a comment thread can attach to an individual piece, a
  whole service, or an entire term — since real queries arise at all
  three levels ("do we have enough copies of this?" vs. "is this
  service's shape right?" vs. "how's this term looking overall?"). This
  is implemented as a single polymorphic relationship (Django's
  `GenericForeignKey`, via `contenttypes`) rather than three separate
  optional foreign keys — a deliberate choice to keep the `Comment`
  model itself clean, at the cost of losing database-level JOIN
  optimisation, which is an acceptable trade-off for a "should have"
  feature.
- **Inbox** — simply every open comment, with no read-receipts or
  @mentions. In a close-knit two/three-person working relationship,
  attention-routing logic would be unnecessary complexity.
- Comments are tied to their subject's lifecycle — if a piece is dropped
  from a shortlist entirely, its comments go with it. This is a
  deliberate, simple default rather than an oversight.

This remains a **"should have,"** not core to MVP.

## 7. Scope Discipline (MoSCoW)

**Must have (the spine)**

- Score CRUD (title, composer/arranger, voicing, language, difficulty/lead-time, duration)
- Term → Service structure, with role slots per service
- Filter scores by voicing
- "Last sung" derived from service history
- Basic liturgical season tagging and filtering

**Should have**

- Full dual-tradition Ordo (liturgical calendar) with moveable feast calculation
- Filter by language
- Physical copy tracking (copies owned, filing location)
- Conductor vs. Librarian roles with distinct permissions
- Comment/query threads

**Nice to have**

- CCLI/copyright licence reporting export
- Choir roster awareness (auto-filtering by available voice parts)
- Smart repertoire suggestions (voicing + season + not-sung-recently)
- Bulk CSV import of a legacy library

## 8. Deliberately Out of Scope

- Multi-tenancy (multiple churches/choirs in one instance)
- Template-editing UI (templates are seeded, not user-editable, for MVP)
- Snapshot history/archive of past generated music lists
- An "active term" flag (superseded by a simple chronological list)
- Threaded (nested) comment replies
- Precise double-choir voicing modelling (e.g. distinguishing which
  parts belong to which of two choirs) — captured accurately in the
  free-text voicing field only, not as structured, queryable data
- Per-role-type permissions (e.g. a distinct user, such as a parish
  secretary, who can edit only the "Hymns" role slot while the
  conductor controls Anthem/Setting). In some real churches, hymn
  selection genuinely sits outside the conductor's remit — but
  modelling that would mean permission checks keyed to individual
  role names rather than a fixed Conductor/Librarian split, a
  meaningfully bigger structural change than MVP calls for. The
  current two-role split (Conductor: full access; Librarian: full
  access to the Score library, read-only on repertoire planning)
  covers the common case.
- Ordo as a liturgical reference tool. Ordo's job is strictly to
  name, date, and colour-tag occasions, for repertoire filtering and
  service labelling — it deliberately does not model readings,
  psalms, propers, or rubrical detail (e.g. whether the Gloria is
  said), regardless of how many calendar traditions it eventually
  covers. That's a separate, mature application domain with
  existing, authoritative tools already serving it well; duplicating
  it would mean building an entirely different application inside
  Precentor, not extending its actual purpose.

Each of these is noted here so that scope decisions read as deliberate
choices, not oversights, when this document is read by an assessor.

## 9. Supporting Documents

- [`docs/user_stories.md`](docs/user_stories.md) — formal user stories
  for the conductor, librarian, and site owner (the church), used to
  validate the finished application against its original intent.
- [`docs/erd.mmd`](docs/erd.mmd) (Mermaid source, renders directly on
  GitHub) — the entity relationship diagram covering Score, Term,
  Service, Service Role, Role Piece, Ordo (Liturgical Occasion), User,
  and Comment, along with notes on a couple of deliberate
  simplifications — notably that role templates are seeded in code
  rather than modelled as a table, and that Comment's polymorphic
  relationship is drawn as three edges there for readability, though
  it's implemented as a single Django `GenericForeignKey` relationship.
- [`docs/models_plan.md`](docs/models_plan.md) — the Django app
  breakdown and field-level model plan translating the ERD into code,
  written ahead of scaffolding the project, and updated as
  implementation revealed corrections (e.g. the fixed-date fix, the
  colour `choices` decision).
- [`docs/design_system.md`](docs/design_system.md) — the visual design
  system: CUBE CSS methodology, cascade layers (not `@import`), design
  tokens, self-hosted typography, and the liturgical accent system.
- [`docs/blocks_backlog.md`](docs/blocks_backlog.md) — the running log
  of Blocks identified during the Compositions sweep across every
  page, deliberately built only after real repetition was observed
  rather than guessed at up front.

## 10. Why This Project

Precentor is grounded in real, lived experience as a church choral
conductor, addressing a genuine and specific pain point (the manual,
repetitive work of planning repertoire and producing music lists) for a
real, identifiable audience (a conductor, working alongside a librarian
or music administrator). Every design decision above has a concrete
"why" behind it, arising from how church music planning actually works,
rather than a generic "library system" template.

---

_Remaining: deployment (Heroku/Postgres, environment variables,
`collectstatic`) and final documentation wrap-up (screenshots of the
finished, styled application; install/run instructions; reconciling
the finished app against `docs/user_stories.md`)._
