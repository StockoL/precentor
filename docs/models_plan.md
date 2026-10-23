# Precentor: App Breakdown and Model Plan

This document turns the [ERD](erd.mmd) into a Django app structure and
a field-level model plan. I wrote it before scaffolding the project and
have kept it up to date since. See the main [README](../README.md) for
the reasoning behind each domain concept.

## App breakdown

| App        | Owns                                                                      | Rationale                                                                                    |
| ---------- | ------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| `accounts` | Roles and who may do what: `permissions.py`, `role_required`, `RoleRequiredMixin`, the `can` context processor | Keeps auth and permissions apart from domain logic, so any app can guard a view by role without depending on `planning` |
| `library`  | `Score`, with its copies and filing fields                                | The reusable "what do we own" side, independent of any term                                  |
| `ordo`     | `LiturgicalOccasion` (seasons, calendar use, moveable feast calculation)  | A self-contained calendar engine that could be reused elsewhere                              |
| `planning` | `Term`, `Service`, `TermMarker`, `ServiceRole`, `RolePiece`               | The core planning workflow: the spine of the MVP                                             |
| `comments` | `Comment` (generic relation via `contenttypes`)                           | Cuts across `planning`, so it's cleaner as its own app than inside `planning`                |
| `core`     | `SiteConfig` (church name, crest, house colour, layout options)           | Site-wide branding and print preferences, not owned by any one term, so not part of `planning` |

Dependencies run one way: `planning` imports from `accounts`,
`library`, `ordo` and `core`, never the reverse. That avoids circular
imports and keeps the spine app easy to reason about and test on its
own. `core`, `library` and `comments` also import their permission
checks from `accounts`, so every app asks the same module who may do
what. `library` and `planning` read the national
calendar from `core`'s settings for their occasion menus; `ordo` reads
nothing from `core` (the suggestion endpoint is told the calendar by
the page), so `core` can import `ordo`'s choices without a cycle.

## Labels and interface words

Every field the forms show has an explicit `verbose_name` wherever the
one Django generates from the field name reads badly (`soprano_parts`
would show as "Soprano parts"; it's labelled "Sopranos"), and
`help_text` with a short example wherever a field needs guidance.
Setting them on the model, not the form, means the label is defined
once and the admin shows it too. The samples below leave most of them
out to stay readable; `models.py` has the full set.

Two models keep names that differ from the words people see:
`ServiceRole` appears as a **slot** and `TermMarker` as a **notice**.
I chose those words in October 2026 (the reasons are in
[`overhaul_plan.md`](overhaul_plan.md), section 8). The model and
field names stay, since renaming them would rename database tables
for no benefit to anyone using the app; `verbose_name` carries the
interface word instead. Every one of these label changes produced a
migration that records the new label and runs no SQL.

## Model field plan

### `accounts.Organisation` and `accounts.User`

```python
class Organisation(models.Model):
    name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)


class Role(models.TextChoices):
    CONDUCTOR = "conductor", "Conductor"
    LIBRARIAN = "librarian", "Librarian"
    VIEWER = "viewer", "Viewer"


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField("email address", unique=True)  # the login; stored lowercase
    name = models.CharField(max_length=150, blank=True)
    organisation = models.ForeignKey(Organisation, null=True, blank=True, on_delete=models.CASCADE, related_name="users")
    role = models.CharField(max_length=20, choices=Role.choices, blank=True)
    is_owner = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
```

I replaced Django's default user before the first migration of the
rebuilt database, because Django can't change `AUTH_USER_MODEL` once
its tables exist. One user belongs to one organisation, so the role
and the owner flag sit on the user rather than on a separate
membership table; memberships across several organisations are future
scope.

Four database constraints keep the rows sensible, each in its own
migration (`accounts/0002` to `0005`) so each can be read and reverted
alone:

- an organisation and a role go together, or neither does (a superuser
  has neither);
- an owner belongs to an organisation;
- an owner is a Conductor or a Librarian, never a Viewer;
- email addresses are unique ignoring case (`UniqueConstraint(Lower("email"))`).
  The field keeps `unique=True` as well, because Django's system check
  requires it on the `USERNAME_FIELD`.

`save()` lowercases the whole address, since `normalize_email` only
lowercases the domain, and the manager's `get_by_natural_key` matches
with `email__iexact`, so sign-in ignores case. `createsuperuser` asks
for an email and a password only, and makes an admin with no
organisation and no role. Users are deleted with their organisation,
and their comments with them.

### Making a church

`accounts/organisations.py` holds the one way a church comes into
being. `create_organisation(name)` makes the `Organisation`, its
`SiteConfig` row, its own Mass and Vespers templates and the use types
Mass, Vespers and General, all inside one transaction, so a failure
part way leaves nothing behind. The starters are plain constants in
that module rather than imported from the old seeding migrations: app
code shouldn't reach into migrations, and those only ever ran on the
original single database. Each church gets copies, so editing its Mass
template changes nobody else's. The admin's form builds the church
before saving it, so the admin calls `set_up_organisation()` with that
object instead; renaming a church there adds nothing.

`SignUpForm` (in `accounts/forms.py`) builds on Django's
`BaseUserCreationForm`, which already matches the two passwords, runs
the site's password validators and hashes the result. It adds the
church's name and the person's name, refuses an address already in use
in any capitals, and saves the church and its first person together:
the person becomes its owner and a Conductor. `SignUpView` signs them
straight in. Sign-up is open to anyone; throttling it comes with the
other abuse protections. Until a church has a term or a score, its
Terms page lists the first steps the person's role allows.

### Every church's data carries its organisation

Each model that holds a church's own data has a required
`organisation` foreign key, deleted with the organisation: `Score`,
`Term`, `SlotTemplate` and `UseType` are given theirs where they're
made, and `Service`, `TermMarker`, `ServiceRole`, `RolePiece` and
`Comment` copy theirs from what they belong to in `save()` (a service
and a notice from their term, a slot from its service, a piece from its
slot, a comment from its term, service or piece). Copying rather than
reaching through the parent means every model can later be limited to
one church with the same `filter(organisation=...)`, and doing it in
`save()` means no view can set it wrongly. The liturgical seasons and
occasions are shared by every church and have none; use types are the
exception in `ordo`, being each church's own words.

Where the app makes something directly, `OrganisationCreateMixin` sets
the organisation from the signed-in person as the form is built, never
from anything posted, so a form can check against the church's own
data. The template form does: names are unique within a church (a
`UniqueConstraint` on organisation and name), so two churches can each
have a Mass, and the form says so plainly, as Django won't check a rule
on a field the form doesn't show.

The column was added empty, filled in, then made required, in that
order, so existing rows were never left without one. The fill-in
migrations share one rule (`accounts/migration_support.py`): rows join
the one organisation if there is one, a new "My church" if there are
none, and the migration stops if there are several. On a database with
no organisations yet, the ready-made Mass and Vespers templates and the
starting use types are removed instead, unless something uses them,
since each organisation will get its own copies when it registers.
`SiteConfig` had its one-to-one link to an organisation filled in the
same way, but stayed optional until every page read its own church's
settings; then the shared `get_solo()` went and the link became
required too (`core/0011`).

### Each church sees only its own

The column only matters if every query uses it, so the rule is that no
view asks a church's model for all its rows. `OrganisationMiddleware`
sets `request.organisation` from the signed-in person, never from the
session, the address or a form, so nobody can choose which church they
look at. The models' managers come from `OrganisationQuerySet`, whose
`for_organisation()` is the one filter every view goes through:

- class-based list, detail, edit and delete views add
  `OrganisationScopedMixin`, which narrows `get_queryset()`;
- function views look an object up with
  `get_object_or_404(own(Model, request), pk=...)`;
- form menus are narrowed in the form's `__init__`, before it checks
  anything, so a hand-made request naming another church's score or use
  type is refused, not just hidden. The score offered for a
  slot comes from `Service.suggested_scores()`, which starts from the
  service's own church;
- a comment's target, and the comment it replies to, must both be the
  church's own, and a reply must be on the same target.

Another church's row is simply not found, so the answer is a 404, never
a 403 that would admit it exists. The only exception is the crest,
which is public branding at an address with the church's id in it.

I finished with a search for every `.objects.` on a church's model
outside tests and migrations. What remains is either already scoped or
only reaches rows through ids taken from the church's own records: the
comment counts on the Terms page, the "last sung" subquery, the
suitability subqueries (the outer query is already the church's), and
the slot reordering, which must list exactly the service's own slots.

### `library.Score`

```python
class Score(models.Model):
    title = models.CharField(max_length=200)
    composer_surname = models.CharField(max_length=100)
    composer_other_names = models.CharField(max_length=100, blank=True)
    arranger = models.CharField(max_length=200, blank=True)
    editor = models.CharField(max_length=200, blank=True)
    voicing = models.CharField(max_length=50)  # free text, e.g. "SATB", "SSATB", "SATB.SATB"
    soprano_parts = models.PositiveSmallIntegerField(default=0)
    alto_parts = models.PositiveSmallIntegerField(default=0)
    tenor_parts = models.PositiveSmallIntegerField(default=0)
    bass_parts = models.PositiveSmallIntegerField(default=0)
    language = models.CharField(max_length=50)
    copies_owned = models.PositiveIntegerField(default=0)
    filing_location = models.CharField(max_length=100, blank=True)
    duration_minutes = models.PositiveIntegerField(blank=True, null=True)
    last_sung_manual = models.DateField(blank=True, null=True)  # history before Precentor
    background = models.TextField(blank=True)
    notes = models.TextField("interpretation notes", blank=True)
    range_soprano = models.CharField(max_length=20, blank=True, validators=[validate_vocal_range])
    # ... range_alto, range_tenor and range_bass the same
    suited_use_types = models.ManyToManyField("ordo.UseType", blank=True, related_name="suited_scores")
    suited_seasons = models.ManyToManyField("ordo.LiturgicalSeason", blank=True, related_name="suited_scores")
    suited_occasions = models.ManyToManyField("ordo.LiturgicalOccasion", blank=True, related_name="suited_scores")

    @property
    def composer(self):
        """"{other_names} {surname}", or just the surname if no other
        names were given. The display form used everywhere else."""
        ...

    @property
    def composer_catalogue(self):
        """Surname first, with any arranger and editor in brackets:
        "Palestrina, Giovanni Pierluigi da (ed. Stockton)"."""
        ...

    class Meta:
        ordering = ["composer_surname", "composer_other_names", "title"]
```

**Editor alongside arranger:** an arranger changes the music, an
editor prepares an edition of it, so they're separate fields. The
library table shows both in the composer column, catalogue style.

**Catalogue order:** scores are ordered by composer surname, then
other names (which keeps the Bachs apart), then title, as a library
catalogue would be.

**Last sung, derived:** never stored, for the same reason as
`Service.status`. `ScoreQuerySet.with_last_sung()` annotates each score
with the latest date of a confirmed piece in a service dated on or
before today; a confirmed piece in a future service is scheduled, not
sung. `last_sung_manual` covers history from before Precentor, and the
later of the two dates wins. It's a `Subquery`, not a `Max()` over a
join, so it can't be thrown off by other joins on the same query, and
it looks `RolePiece` up by name with `apps.get_model()` because
`library` mustn't import from `planning`. Each side of `Greatest()` is
wrapped in `Coalesce()`, because SQLite returns NULL when any argument
is NULL while PostgreSQL ignores it; the coalescing gives the same
answer on both.

**Background, notes and vocal ranges:** these give the score page
something the library table can't show. Each range is two notes in
scientific pitch notation from low to high, such as `A3–E5`.
`library/validators.py` checks the format and converts each note to
a semitone count, so a range written the wrong way round is refused
with its own message. `Score.clean()` then stores every range in one
tidy form (`a3 - e5` becomes `A3–E5`); a `ModelForm` runs it after
each field's own validators, so it only ever sees valid ranges.

**Freehand use types:** the score form has an extra, non-model field,
`new_use_types`, for comma-separated names. `ScoreForm` matches each
case-insensitively against existing `UseType`s, creates any new ones
and adds them all to the score. It overrides `save()` so this happens
however the form is saved, including later through `save_m2m()` after
`commit=False`. Seasons and occasions stay pick-only.

**Search and voicing:** `ScoreQuerySet.search(query)` needs every word
to match somewhere in the title, composer names, arranger or editor (an
AND of ORs), and `with_voicing(voicing)` takes one voicing or `"mixed"`
for scores with all four parts. The view stays thin and each piece is
tested on its own.

**Composer split, surname required:** `composer` started as one
free-text field. It's now `composer_surname` (required) and
`composer_other_names` (optional), so cataloguing and searching by
surname always work, even when the full name isn't known. `composer`
lives on as a read-only property for display and `__str__`, not a
database column, so admin `search_fields` and any filtering have to
use the two real fields.

**`lead_time_tag` removed:** I dropped it as micromanagement. It added
a rehearsal-scheduling dimension that nothing else in the app used or
showed.

**Three-tier suitability tagging, ranking not filtering:**
`suited_use_types`, `suited_seasons` and `suited_occasions` are three
different kinds of fact (the type of service, a broad season of the
calendar, a specific named day), not one generic tag.
`ScoreQuerySet.ranked_by_suitability(occasion=, season=, use_type=)`
annotates an `is_suited` flag and sorts matching scores to the top. It
never filters, because an untagged score might still be the right
choice and the app has no way to know otherwise. Each condition is a
`pk__in` subquery ("is this score among those tagged X?"); an earlier
version joined through the tags, which listed a score with several
tags once per tag. Each field has `help_text` with examples ("Mass,
Vespers, General use"), since the `UseType` and `LiturgicalSeason`
lists are otherwise invisible until they have entries. `ordo`'s
`0004_seed_use_types_and_seasons` data migration seeded a starter set
of both, revised for the Catholic-only scope by `0008` to `0010`. Use
types now belong to each church, and a new church gets Mass, Vespers
and General from `create_organisation()` (see "Making a church"). Full
`LiturgicalOccasion` data is a separate, larger content task, noted
below.

**Voicing as free text:** an earlier version of this plan gave
`voicing` a fixed `choices` list (SATB, SATTB, unison and so on). I
dropped it because voicing isn't a small closed set. It's a compact
notation with endless combinations (SSATB, SATB.SATB for double choir),
which a fixed dropdown can't represent. So `voicing` stays free text
for accurate display, while `soprano_parts`, `alto_parts`,
`tenor_parts` and `bass_parts` hold the part _counts_. Those make
filtering reliable ("needs a tenor at all", "exactly SSATB") without
parsing free text.

**Out of scope:** precise double-choir modelling, such as recording
which parts belong to which choir. The part counts describe a single
choir's texture; double-choir pieces are recorded accurately only in
the free-text `voicing` field. The README lists this as a scope limit.

### `ordo.LiturgicalOccasion`

```python
COLOUR_CHOICES = [
    ("violet", "Violet"),
    ("red", "Red"),
    ("green", "Green"),
    ("white", "White/Gold"),
    ("rose", "Rose"),
    ("black", "Black"),
]

CALENDAR_USE_CHOICES = [
    ("current", "Ordinary Form (Novus Ordo)"),
    ("historic", "Extraordinary Form (1962)"),
]

class LiturgicalSeason(models.Model):
    name = models.CharField(max_length=50)

class UseType(models.Model):
    name = models.CharField(max_length=50)

NATIONAL_CALENDAR_CHOICES = [
    ("general_roman", "General Roman Calendar"),
    ("england", "England"),
    ("wales", "Wales"),
]

class LiturgicalOccasion(models.Model):
    name = models.CharField(max_length=100)
    key = models.CharField(max_length=100, blank=True)  # e.g. "george_of_lydda_martyr"
    calendar_use = models.CharField(max_length=20, choices=CALENDAR_USE_CHOICES, default="current")
    calendar = models.CharField(max_length=20, choices=NATIONAL_CALENDAR_CHOICES, default="general_roman")
    rank = models.CharField(max_length=20, choices=RANK_CHOICES, blank=True)  # solemnity ... class_4
    precedence = models.CharField(max_length=4, choices=OF_PRECEDENCE_CHOICES, blank=True)  # "1" to "13"
    date_rule = models.CharField(max_length=50, blank=True)  # e.g. "date_of_ordinary_time"
    date_rule_args = models.JSONField(default=list, blank=True)  # e.g. [0, 5]
    date_offset_days = models.SmallIntegerField(default=0)
    transfers = models.JSONField(default=list, blank=True)
    is_proper_of_time = models.BooleanField(default=False)
    shares_with_memorials = models.BooleanField(default=False)
    is_moveable = models.BooleanField(default=False)
    fixed_month = models.PositiveSmallIntegerField(blank=True, null=True)
    fixed_day = models.PositiveSmallIntegerField(blank=True, null=True)
    easter_offset_days = models.IntegerField(blank=True, null=True)
    colour = models.CharField(max_length=20, choices=COLOUR_CHOICES, blank=True)
    season = models.ForeignKey(LiturgicalSeason, null=True, blank=True, on_delete=models.SET_NULL, related_name="occasions")

    def date_for_year(self, year):
        """Resolves either a fixed or moveable occasion to an actual
        date for a given calendar year, via calculate_easter_sunday()."""
        ...


def occasion_for_date(target_date, calendar_use, national_calendar="general_roman"):
    """Reverse lookup: the occasions kept on target_date, the day's
    celebration first. Works out the whole year with the order of
    precedence (ordo/calendar.py, or ordo/calendar_1962.py for 1962).
    Returns a list, because zero, one or more occasions can be kept."""
    ...
```

**Fixed dates as month and day:** the original plan used a single
`fixed_date = DateField()` for non-moveable occasions. That was wrong:
a `DateField` stores one year's date, but Christmas Day falls on the
same month and day every year. I replaced it with `fixed_month` and
`fixed_day`, mirroring how moveable occasions already work through
`easter_offset_days`. Both resolve to a real date only when
`date_for_year(year)` is called; no year is ever stored.

**Colour as a fixed list, the opposite of voicing:** liturgical colour
is a small, fixed vocabulary (violet, red, green, white, rose). There's
nothing like "SATB.SATB" that would need free text. I added `choices`
so every stored value maps predictably onto a CSS design token name
(see `docs/design_system.md`), and a typo like `"Purple"` for
`"violet"` can't quietly break that mapping.

**Out of scope:** Ordo only names, dates and colours occasions, for
repertoire suggestions and service labels. It doesn't model readings,
psalms, propers or rubrics (such as whether the Gloria is said), and
won't even if it later covers other calendars. See the README's
out-of-scope list.

**Catholic only:** an earlier version of this plan gave
`LiturgicalSeason`, `LiturgicalOccasion`, `Term` and `Service` a
`tradition` field (Catholic or Church of England), with
`Service.effective_tradition()` resolving the override. I removed it in
October 2026. Precentor is single-tenant, and one church follows one
tradition, so a per-term choice added a field to every form, a second
set of seed data and a second set of tests without helping any real
user. `ordo/0005` deleted the Church of England rows while the column
still identified them, then `ordo/0006` and `planning/0005` dropped the
field. The data and schema changes are separate migrations because
Postgres can refuse to alter a table with pending trigger events in
the same transaction. The README lists a second tradition as future
work.

**Real calendars, and precedence (October 2026):** the fields `key`,
`calendar`, `rank`, `precedence`, `date_rule`, `date_rule_args`,
`date_offset_days` and `transfers` let `ordo` hold the real Ordinary Form and 1962 calendars,
with national calendars (England, Wales) that add days to the general
calendar or override its days by sharing their `key`. A key is unique
within one calendar and form; occasions entered by hand have none.
`precedence` is the level in the Table of Liturgical Days, which
decides what's celebrated when two days fall together. Black joins the
colours for 1962.

**Date rules (`ordo/dates.py`):** `date_for_year()` now works out a
named rule (ported from romcal) and applies the occasion's transfers.
Some rules depend on the national calendar, so it takes one; a general
day such as Corpus Christi falls on the Thursday in the General Roman
Calendar and on the Sunday in England. `date_in()` takes a prepared
`YearDates`, so working out a whole year can share one. I compared the
port with romcal's own dates for every day in scope, in three
calendars, from 2020 to 2040: 14,448 dates, eight different. All eight
are moves "to the day after Divine Mercy Sunday" or "to the day before
Palm Sunday", where romcal counts the day from the original date (so
St George in 2022 lands on Divine Mercy Sunday itself, still inside
the Easter Octave). Precentor follows the rule as the data states it.

**Precedence (`ordo/calendar.py`):** `occasion_for_date()` now returns
the day's celebration first, then anything kept alongside it, after
working out the whole year: impeded days are left out and an impeded
solemnity moves. Two flags support it. `is_proper_of_time` puts the
seasons ahead of a saint's day of the same rank, and
`shares_with_memorials` marks the one memorial (the Immaculate Heart
of Mary) that keeps another memorial on its day.

**Where the rows come from:** `manage.py load_calendar`
(`ordo/calendar_data.py`) loads the General Roman, England and Wales
calendars from `ordo/data/romcal/`, and the 1962 calendar from
`ordo/data/missalemeum/` with England's and Wales's 1962 days from
`ordo/data/lms/`, matching each row by form, calendar and key,
so it can be run again safely. A row gone from the files is removed,
unless a service or score uses it, when it's kept and reported. Occasions a conductor enters
by hand have no key, take no part in precedence and are never touched
by a load. Precedence level 12 (optional memorial) exists only so a
national row can make a general memorial optional; the engine leaves
level 12 out.

**The 1962 rows** use the same model. Their `rank` is `class_1` to
`class_4`; `precedence` stays blank, because the 1962 rules
(`ordo/calendar_1962.py`) work it out from Missalemeum's Table of
Precedence. A saint's day has a fixed month and day; the Proper of
Time uses one date rule, `tempora_1962`, which finds the day in that
year's layout of the season's blocks; and Christ the King uses
`christ_the_king_1962`, the last Sunday of October.
`occasion_for_date()` chooses the Ordinary Form or the 1962 engine by
`calendar_use`.

**Choosing occasions in forms:** `LiturgicalOccasion.objects.listable()`
gives the occasions a conductor can pick for one national calendar:
the general calendar in both forms with the national rows in place of
the ones they override, plus occasions entered by hand, but no other
country's days, no fourth-class days and no optional memorials. The
service form's occasion menus and the score form's "suitable for"
occasions use it, with the church's calendar from Settings, and keep
anything already chosen even if it's no longer listable.
`choice_label` adds "(1962)" to the 1962 days' names in those menus
(`ordo/fields.py`).

The design, its sources and the order of work are in
[`calendar_plan.md`](calendar_plan.md).

**Calendar use, and the reverse lookup:** `calendar_use` separates the
Ordinary Form (`current`) from the 1962 Extraordinary Form
(`historic`); some churches, Catholic oratories for example, use both.
`LiturgicalSeason` and `UseType` exist for the three-tier `Score`
suitability tagging above. `LiturgicalOccasion.season` is the link that
lets a season-level tag ("Advent") and a day-level tag ("Advent Sunday
4") match each other. `occasion_for_date()` is the reverse of
`date_for_year()`: given a date, which occasions fall on it. The
service form uses it to suggest an occasion from the date.

### `planning.Term`

```python
class Term(models.Model):
    name = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    calendar_use = models.CharField(max_length=20, choices=CALENDAR_USE_CHOICES)
    comments = GenericRelation("comments.Comment")

    class Meta:
        ordering = ["start_date"]

    def get_absolute_url(self):
        ...

    def completion_summary(self):
        """Aggregates Service.status counts across this term's services,
        for the Terms page. See README §3.3."""
        ...
```

### `planning.Service`

```python
class Service(models.Model):
    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name="services")
    date = models.DateField()
    service_type = models.CharField(max_length=50)  # free text, e.g. "Sung Mass"
    occasion = models.ForeignKey(
        "ordo.LiturgicalOccasion", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="services",
    )
    additional_occasions = models.ManyToManyField(
        "ordo.LiturgicalOccasion", blank=True, related_name="also_relevant_services",
    )
    calendar_use = models.CharField(max_length=20, choices=CALENDAR_USE_CHOICES, null=True, blank=True)
    slot_template = models.ForeignKey(
        "SlotTemplate", null=True, blank=True, on_delete=models.SET_NULL, related_name="services",
    )  # the template whose slots it uses now
    hymns = models.CharField(max_length=200, blank=True)
    psalm = models.CharField(max_length=100, blank=True)
    comments = GenericRelation("comments.Comment")

    class Meta:
        ordering = ["date"]

    def effective_calendar_use(self):
        return self.calendar_use or self.term.calendar_use

    def use_template(self, template, replace=False): ...  # see SlotTemplate
    def move_slot(self, role, step): ...  # Move up / Move down
    def set_slot_order(self, pks): ...  # after a drag; ValueError unless pks are exactly its slots

    @property
    def status(self):
        """Derived, not stored: not_started / in_progress / complete."""
        ...

    @property
    def status_label(self):
        """"Not started" / "In progress" / "Complete", from STATUS_LABELS."""
        ...

    def music_list_rows(self, draft=False):
        """Rows for the music list. N/A slots are always skipped;
        unconfirmed slots are skipped in the public version and shown
        as TBC in draft mode. See README §4."""
        ...
```

**`hymns` and `psalm` as plain fields, not slots:** these were always
meant as simple text fields, separate from the slots
(`ServiceRole` and `RolePiece`) used for the Mass setting, motets and
so on. A hymn number or psalm reference doesn't need a shortlist, a
confirmation step or a link to `library.Score`.

**Status labels:** `status` returns a raw value, which templates use
for CSS classes (`badge--not_started`) and comparisons. Because it's
derived, not a field with `choices`, Django's `get_status_display()`
doesn't exist for it, so `Service.STATUS_LABELS` and the
`status_label` property do the same job by hand. Templates show the
label and never the raw value.

**Dates in `__str__`:** `Service.__str__` ("Sung Mass — Sun 11 Jan
2026") and `TermMarker.__str__` format their dates with Django's
`date_format()`, which reads `DATE_FORMAT` from the project's format
module, `precentor_project/formats/en_GB/formats.py`. That module,
found through `FORMAT_MODULE_PATH`, is the one place the app's date
style is set; templates use a bare `|date` filter to follow it.

**`GenericRelation` on the commentable models:** `Term`, `Service` and
`RolePiece` each have `comments = GenericRelation("comments.Comment")`.
It adds no database column and needs no migration. It lets code write
`term.comments.all()`, and it makes Django delete a target's comments
when the target is deleted, which is the pattern Django's own docs
recommend alongside a `GenericForeignKey`. It does mean `planning`
refers to `comments`, an exception to the one-way rule above, but
`comments.models.Comment` still knows nothing about `planning`'s
models. The interface only offers comments on terms and services; a
question about a piece goes in its service's thread, though the model
would still accept one on a `RolePiece`.

### `planning.TermMarker`

```python
class TermMarker(models.Model):
    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name="markers")
    date = models.DateField()
    text = models.CharField("notice", max_length=200)

    class Meta:
        ordering = ["date"]
```

Shown in the interface as a **notice**. It lets a conductor put a
one-off line of text at a date in a term (half-term, a retreat,
anything that isn't a service) for the public music list (see README
§4). The music list view merges `Term.services` and `Term.markers`
into one sequence ordered by date, tagging each item with its type so
the template knows how to render it. Nothing else in the codebase
merged two querysets like this, so I wrote it from scratch.

### `planning.ServiceRole`

```python
class ServiceRole(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="roles")
    role_name = models.CharField("slot", max_length=50)  # e.g. "Introit", "Offertory motet"
    is_not_applicable = models.BooleanField("not needed (N/A)", default=False)
    position = models.PositiveIntegerField(default=0)  # a new slot gets the next number

    class Meta:
        ordering = ["position", "id"]

    def deletion_summary(self): ...  # pieces and comments removing it takes with it
```

Shown in the interface as a **slot**. Slot names are free text; see
the README (§3.2) for why. `position` holds the order the conductor
gives the slots. Moves renumber the service's slots from 1, and the
migration that added it (`planning/0011`) numbered existing slots in
the order they were made, which was the order shown before. A drag
sends the whole new order, not one move, and `set_slot_order` refuses
a list that isn't exactly the service's slots, so a page that's out of
date can't lose or duplicate one.

### `planning.SlotTemplate`

```python
class SlotTemplate(models.Model):
    name = models.CharField(max_length=50, unique=True)
    slot_names = models.TextField("slots")  # one slot per line, in order

    @property
    def slots(self): ...  # trimmed, blank lines dropped, each name once

    def apply_to(self, service): ...  # adds the slots the service lacks
```

A template is a named list of slots that a conductor adds to a service
in one go. Each church gets its own Mass and Vespers when it's made
(see "Making a church"); they began as a data migration
(`planning/0009`) from before there were churches. The slots are lines of text, not a related table: the
form is a textarea that needs no JavaScript, and order is simply line
order. Applying one copies the names into new `ServiceRole` rows,
skipping names the service already has (ignoring case). The slots keep
no link to it, so editing a template never changes services already
planned. `Service.slot_template` only records which template the
service uses, so that choosing a different one can ask first and then
replace the slots (`Service.use_template(replace=True)`), keeping any
slot with pieces proposed.

### `planning.RolePiece`

```python
class RolePiece(models.Model):
    service_role = models.ForeignKey(ServiceRole, on_delete=models.CASCADE, related_name="pieces")
    score = models.ForeignKey("library.Score", on_delete=models.PROTECT, related_name="role_pieces")
    is_confirmed = models.BooleanField(default=False)
    comments = GenericRelation("comments.Comment")
```

**History state:** `RolePiece.history_state` is `sung` once confirmed
for a service dated on or before today, `scheduled` if confirmed for
a later one, and `proposed` otherwise, with `history_label` for
display, the same pattern as `Service.status`. It uses the same
"today" as `Score.objects.with_last_sung()`, so a score's history and
its last-sung date always agree. The score page lists a piece's
history through the reverse relation `score.role_pieces`, so `library`
still doesn't import from `planning`.

### `comments.Comment`

```python
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

class Comment(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    body = models.TextField("comment")
    is_open = models.BooleanField(default=True)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="replies"
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    target = GenericForeignKey("content_type", "object_id")
    created_at = models.DateTimeField(auto_now_add=True)
```

### `core.SiteConfig`

```python
LAYOUT_STYLE_CHOICES = [
    ("columns", "Newspaper columns"),
    ("simple", "Simple single column"),
]

class SiteConfig(models.Model):
    organisation = models.OneToOneField("accounts.Organisation", on_delete=models.CASCADE, related_name="settings")
    church_name = models.CharField(max_length=200, blank=True)
    crest = models.BinaryField(blank=True, default=b"", editable=False)  # the image itself
    crest_type = models.CharField(max_length=20, blank=True, editable=False)  # "image/png" or "image/jpeg"
    crest_version = models.CharField(max_length=12, blank=True, editable=False)  # a fingerprint of the image
    crest_style = models.CharField(max_length=10, choices=CREST_STYLE_CHOICES, default="logo")  # logo or banner
    house_accent_colour = models.CharField(max_length=7, default="#8b1a2b", validators=[validate_hex_colour])
    national_calendar = models.CharField(max_length=20, choices=NATIONAL_CALENDAR_CHOICES, default="general_roman")
    layout_style = models.CharField(max_length=20, choices=LAYOUT_STYLE_CHOICES, default="columns")
    show_hymns_psalm = models.BooleanField(default=True)

    @classmethod
    def of(cls, organisation):
        config, _ = cls.objects.get_or_create(organisation=organisation)
        return config

    @classmethod
    def national_calendar_of(cls, organisation_id):
        ...  # reads only; the default calendar when there's no row yet
```

**One row per church.** This began as a singleton, with `pk` pinned to
`1` and a `get_solo()` that every view used. Now each organisation has
its own row, made with the defaults by `SiteConfig.of()` the first time
it's needed, so a new church needs no setting up. The forms use
`national_calendar_of()` instead, because building a form shouldn't
create a row: it only reads, and falls back to the general calendar.
The one-to-one link means the database itself refuses a second row for
the same church, so the admin no longer has its own one-row check.

**The national calendar is a site setting.** It belongs to the church,
like its name and crest, and one church follows one national calendar,
so it lives on `SiteConfig` and not on a term or service. `core`
imports the choices from `ordo`; `ordo` imports nothing from `core`.

**The accent colour is checked as hex.** `validate_hex_colour` only
accepts `#` and six hex digits. The value goes into an inline `style`
on the music list, and autoescaping stops HTML but not extra CSS, so a
value like `red; background: url(...)` must never be saved. The colour
picker can only send hex anyway; the validator covers the admin and
anything posted by hand.

**The crest is kept in the database.** It began as an `ImageField`
saved to a `media/` folder, but hosts such as Render and Heroku wipe
their disk on every deploy, so an uploaded crest would vanish. The
image's bytes now sit in a `BinaryField`, which is fine for one small
image: every upload is processed to a fixed size, from a few kilobytes
for a simple logo to a few hundred for a photographic banner.
`set_crest()` stores an image with its type and a 12-character SHA-256
fingerprint; `clear_crest()` empties all three. A data migration
(`core/0007`) copied any existing crest across before the file field,
and the media settings it needed, were removed.

**Two styles.** Churches use both a crest or logo shown beside the
name and banner artwork that carries the name, so `crest_style`
records which. `core/imaging.py` processes an upload to suit it: a
banner is cropped to 4:1 at 1600 by 400, and a logo keeps its own shape,
fitted inside 600 by 600 and never enlarged. Changing the style asks
for a new image, since one shape looks wrong in the other's place. The
form also caps uploads at 5 MB, so a huge photo fails before Pillow
opens it. The processing runs in the form, not in `Model.save()`, so a
bad upload shows up as an ordinary form error.

**The crest is served publicly at a versioned address.**
`core.views.crest` sends the stored image from
`/settings/crest/<fingerprint>/` with a year-long `public, immutable`
cache. It's public branding printed on the music list, so it needs no
login, and a new image gets a new address, so browsers can keep it
without ever showing an old one. `SiteConfig.crest_url` builds the
address and `crest_layout` tells the music list which layout to use.

## Template organisation

Templates are kept **per app** (for example
`library/templates/library/`), not centralised in one project-level
`templates/` folder, so each app is self-contained and its templates
travel with it, in line with the one-way dependencies above. The one
exception is `templates/base.html` at the project root, which every
app shares.

## Decisions worth remembering when writing the code

- `RolePiece.score` uses `on_delete=models.PROTECT`: a Score can't be
  deleted while planning history still refers to it, since "last
  sung" depends on that history.
- `Service.status` is a `@property`, computed on the fly, not stored.
  It stays derived, as the README sets out (§3.3), and a stored field
  can't go stale.
- `ServiceRole.is_not_applicable` being `True` counts as a decision
  (the same as a confirmation) for `Service.status`, not as missing
  data.
- `ScoreDeleteView` catches `ProtectedError` (raised by the
  `on_delete=PROTECT` on `RolePiece.score`) and shows a friendly
  message instead of a server error. I found that gap during the
  visual design pass; I hadn't anticipated it.
- `Term` deletion doesn't get the same protection. `Service.term` uses
  `on_delete=CASCADE`, so deleting a term takes its whole planning
  history with it, a different choice from `RolePiece.score` on
  purpose.
- A `Comment` can only be deleted once it's closed (`is_open` is
  `False`). `comments.views.delete_comment` enforces this on the
  server, not just by hiding the button, so a comment can't be thrown
  away while its question is still open. Deleting a parent removes its
  replies too, through `on_delete=CASCADE` on `Comment.parent`.
- `Term.calendar_use` is required, which covers the usual case of one
  calendar. `Service.calendar_use` is an optional override, resolved
  by `effective_calendar_use()`. That supports churches that use more
  than one calendar in the same term (Catholic oratories with both EF
  and NO Masses, for example) without making every church set an
  override.
- `Service.occasion` stays a single foreign key, which drives the
  occasion's colour accents as before. `Service.additional_occasions`
  is a separate many-to-many for when more than one occasion falls on
  a date. I chose it over turning `occasion` itself into a
  many-to-many, which would have meant re-testing everything that
  reads `service.occasion` as a single value. The public music list
  shows a second occasion as a smaller label under the main one.
- Permissions live in `accounts/permissions.py`, not in each app: one
  function per question (`can_plan`, `can_edit_library`, `can_comment`,
  `can_manage_settings`, `can_delete_comments`), each taking a user and
  returning True or False. Function views use `@role_required(check)`
  and class-based views `RoleRequiredMixin` with `permission = check`;
  templates read the same answers through the `can` context processor.
  A signed-in person without the right gets a 403, and a superuser has
  no role inside the app. A role is a field on the user; while the
  custom user was being built it was a Django Group, and only the
  private `_role` function changed when it moved. Owning the
  organisation is a flag, checked by `can_manage_organisation`.
- `SiteConfig.layout_style` only changes the **public** music list.
  Draft mode always shows the plain single-column list, since draft
  is for a conductor to scan what's still TBC, not to preview the
  printed layout.
