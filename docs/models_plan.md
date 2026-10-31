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

Five database constraints keep the rows sensible, each in its own
migration (`accounts/0002` to `0006`) so each can be read and reverted
alone:

- an organisation and a role go together, or neither does (a superuser
  has neither);
- an owner belongs to an organisation;
- an owner is a Conductor or a Librarian, never a Viewer;
- an organisation has at most one owner (a `UniqueConstraint` on the
  organisation, counting only rows where `is_owner` is true), so "the
  owner" is always one person and handing over is a swap;
- email addresses are unique ignoring case (`UniqueConstraint(Lower("email"))`).
  The field keeps `unique=True` as well, because Django's system check
  requires it on the `USERNAME_FIELD`.

`save()` lowercases the whole address, since `normalize_email` only
lowercases the domain, and the manager's `get_by_natural_key` matches
with `email__iexact`, so sign-in ignores case. `createsuperuser` asks
for an email and a password only, and makes an admin with no
organisation and no role. Users are deleted with their organisation.
Someone who deletes their own account leaves their comments behind:
`Comment.author` is set to empty (`SET_NULL`), and `author_name` shows
"A former member", so threads still read sensibly but nothing identifies
them. Removing someone from a church doesn't
delete them: it sets `is_active` to false, so their comments keep their
name, and Django's sign-in refuses them from their next request.

### Members and invitations

`accounts.Invitation` lets one person join a church in a given role. It
has the organisation, the role, an optional note ("who it's for"), who
made it, when, an `expires_at` seven days later, and `used_at` and
`used_by`. `Invitation.make()` creates a random secret with
`secrets.token_urlsafe(32)` and stores only its SHA-256 fingerprint
(`token_hash`, unique), so the database can't be turned back into
working links; the link is shown to the owner once, carried from the
form to the next page in the session and removed as it's shown.
`Invitation.find()` matches a link's fingerprint against unused,
unexpired invitations, and `use()` claims one with a single conditional
`UPDATE`, so two people using the same link at once can't both get in.
Cancelling deletes the row; a used one stays, as the record of who
joined.

`JoinForm` shares a base, `NewPersonForm`, with `SignUpForm`, so the
name, email and password rules are the same. Joining creates the person
in the invitation's church and role, and if the link was claimed first
the whole save is undone (`Invitation.Gone` inside `transaction.atomic`).

The Members page lists the church's active people for everyone, with
names, roles and the owner badge. The owner also sees addresses,
invitations waiting to be used, former members, and the controls:
change a role (`RoleForm`, which leaves Viewer out of the owner's own
menu), remove and restore, make someone else the owner, and make a
reset link. `User.hand_ownership_to()` clears the old owner's flag
before setting the new one, inside a transaction, as the one-owner
rule would refuse two owners even for a moment. Reset links are
Django's own signed tokens from `default_token_generator`, so nothing
is stored and a link stops working once used, once the person signs
in, or after three days. Django's "email me a link" pages are left out
of the URLs, as Precentor sends no email; everyone can change their own
password from the user menu. Invitation and reset links have a Copy
link button (`copy-link.js`), and the read-only box they sit in still
works without JavaScript.

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
straight in. Sign-up is open to anyone, up to five churches an hour
from one network address. Until a church has a term or a score, its
Terms page lists the first steps the person's role allows.

### Leaving

- **A member deletes their own account** from a link on the Change
  password page, after giving their password (`DeleteAccountForm`).
  They're signed out, the account is deleted and their comments stay as
  "A former member". The owner can't do this: a church always needs an
  owner, so they're told to hand ownership over or delete the church.
- **The owner deletes the church** from a link at the foot of Settings.
  The page shows how much will go (`Organisation.contents()`) and asks
  for the church's name, ignoring capitals and spaces at the ends. A
  planned piece protects its score (`PROTECT`), which made deleting a
  church fail, so `Organisation.delete()` deletes the church's pieces
  first and then the rest, in one transaction. The admin's delete page
  goes through it too; its "delete selected" action doesn't, so it
  still refuses a church with planned pieces.
- **A privacy page** (`/privacy/`, linked from every page's footer and
  from sign-up) says what's kept, the cookies, the limits on trying,
  where it's hosted and how to leave, and names each church's owner as
  the person to ask.

### Caching, cookies and limits

Nothing a church owns is cached on the server. The one cache is a table
in the database (`DatabaseCache`, made by `createcachetable` in the
build), and it holds only counts of attempts, so both worker processes
share them and they survive a restart. `accounts/throttling.py` keeps
each count under a SHA-256 fingerprint of what's counted, so the table
never holds an email address in plain text, and sets each count's
expiry itself, since `cache.incr()` would fall back to the default.

- **Signing in:** after five wrong passwords for one address, the sign-in
  form refuses that address for 15 minutes after the last one, before the
  password is checked, and `SignInView` answers 429. Signing in clears
  the count, and capitals don't get round it.
- **Registering:** after five churches registered from one network
  address in an hour, `SignUpView` refuses the next with a 429. Only
  churches actually made count. The address is the last entry of
  `X-Forwarded-For`, the one the host's proxy adds, as earlier entries
  could be made up. That Render's proxy adds the visitor's address last
  is my reading of how such proxies work, not something I've confirmed
  from Render's documentation or the live logs.

`NoStoreWhenSignedInMiddleware` gives every response to someone signed
in `Cache-Control: private, no-store`, decided before the view runs so
logging out is covered, and leaves alone a response that sets its own
caching, which is how the crest keeps its year-long public cache. The
cookie settings are written out in `settings.py` even where they're
Django's defaults: the session cookie is HttpOnly, both cookies are
SameSite=Lax, and both are Secure once deployed. The CSRF cookie stays
readable by scripts because `ajax.js` sends its value with each request.

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

That search was a one-off, so a test now does the same job every time
the suite runs (`precentor_project/test_isolation.py`). It builds two
churches with one of everything, every piece of the second's text
marked `B-ONLY`, and then:

- finds the models that hold a church's data by their `organisation`
  field and fails if the builder doesn't make one of each, so a new
  model can't be missed;
- opens and posts to every address with an id in it, as the first
  church's owner, aimed at the second church's rows: nothing may be
  shown, and every one of the second church's rows must be unchanged
  afterwards;
- opens every page without an id, and every one of the first church's
  own pages, and fails if `B-ONLY` appears anywhere, which catches leaks
  through lists, menus and the piece picker;
- fails if any route in the project isn't covered by one of those
  checks or a written exemption (the public crest, and the two pages
  reached by a token).

Breaking `for_organisation()` on purpose makes it fail at once, naming
each route that leaked.

### `library.Score`

```python
class Score(models.Model):
    title = models.CharField(max_length=200)
    composer_surname = models.CharField(max_length=100)
    composer_other_names = models.CharField(max_length=100, blank=True)
    arranger = models.CharField(max_length=200, blank=True)
    editor = models.CharField(max_length=200, blank=True)
    voicing = models.CharField(max_length=50, blank=True)  # free text, e.g. "SATB", "SSATB", "SATB.SATB"
    soprano_parts = models.PositiveSmallIntegerField(default=0)
    alto_parts = models.PositiveSmallIntegerField(default=0)
    tenor_parts = models.PositiveSmallIntegerField(default=0)
    bass_parts = models.PositiveSmallIntegerField(default=0)
    language = models.CharField(max_length=50, blank=True)
    copies_owned = models.PositiveIntegerField(default=0)
    filing_location = models.CharField(max_length=100, blank=True)
    duration_minutes = models.PositiveIntegerField(blank=True, null=True)
    last_sung_manual = models.DateField(blank=True, null=True)  # history before Precentor
    background = models.TextField(blank=True)
    notes = models.TextField("interpretation notes", blank=True)
    text = models.TextField(blank=True)  # the words, for the pew sheet
    translation = models.TextField(blank=True)
    translation_credit = models.CharField(max_length=200, blank=True)
    range_soprano = models.CharField(max_length=20, blank=True, validators=[validate_vocal_range])
    # ... range_alto, range_tenor and range_bass the same
    suited_use_types = models.ManyToManyField("ordo.UseType", blank=True, related_name="suited_scores")
    suited_seasons = models.ManyToManyField("ordo.LiturgicalSeason", blank=True, related_name="suited_scores")
    suited_occasions = models.ManyToManyField("ordo.LiturgicalOccasion", blank=True, related_name="suited_scores")
    import_batch = models.ForeignKey("ScoreImport", null=True, blank=True, on_delete=models.SET_NULL, related_name="scores")

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

**Texts typed by the church:** `text`, `translation` and
`translation_credit` hold the words a score sets, for the pew sheet. The
liturgical Latin is public domain but many translations aren't, so the
credit has a field of its own and the form asks for only texts the
church is entitled to reproduce; Precentor doesn't claim to know a
text's licence. Many composers set the same words, and a shared `Text`
model would save typing them twice, but fields on `Score` come first:
moving them into a model later is a routine data migration.
`needing_text()` finds scores with no text that have been planned into a
motet or antiphon slot, the ones a pew sheet would print, for the
Library completeness page. It reaches the slot through
`role_pieces__service_role__kind`, a lookup by name, so `library` still
doesn't import from `planning`.

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

**Voicing and language optional:** only the title and the
composer's surname are needed now. A church importing an old catalogue
rarely has every voicing and language to hand, and the alternative, a
placeholder such as "Unknown", would fill the Voicing and Language
filters with junk. Each filter gains an "(unspecified)" choice with its
count instead, so the gaps are easy to find and fill. Migration `0018`.

### `library.ScoreImport`

```python
class ScoreImport(models.Model):
    PENDING, KEPT = "pending", "kept"

    organisation = models.ForeignKey("accounts.Organisation", on_delete=models.CASCADE, related_name="score_imports")
    created_by = models.ForeignKey("accounts.User", null=True, on_delete=models.SET_NULL, related_name="score_imports")
    created_at = models.DateTimeField(auto_now_add=True)
    original_filename = models.CharField(max_length=255)
    status = models.CharField(max_length=10, choices=[(PENDING, "Pending"), (KEPT, "Kept")], default=PENDING)
    report = models.JSONField(default=dict, blank=True)  # skipped rows, likely duplicates, encoding

    def keep(self): ...
    def remove(self): ...
```

One spreadsheet brought into a church's library (migration `0019`). Its
scores are ordinary scores from the moment they're saved, linked back
through `Score.import_batch`. While the import is pending it can be
removed as a whole, in case the file wasn't the one meant; `keep()`
closes it, and from then on scores are only deleted one by one.

**Removing keeps what's in use:** `remove()` runs in one transaction.
Scores already planned into a service are unlinked and kept, because
`RolePiece.score` is `PROTECT` and a service's history matters more than
a tidy undo; the rest are deleted, then the batch. It returns both
counts, which the confirmation message reports.

**`created_by` is `SET_NULL`:** if the person who imported leaves, the
import and its scores stay with the church. Removing a pending import is
open to whoever made it, while they can still edit the library, or any
Conductor (`can_remove_import`).

**The format lives in code, not the database:** `library/importing.py`
holds `COLUMNS`, the one list of headers that the template download, the
header check, the import page's example and the export all read. Each
row is checked by `ScoreImportRowForm`, a `ModelForm` over just those
fields, so the import can't accept a value the score form would refuse.
Good rows are written with one `bulk_create` inside the same transaction
as the batch, so a failure never leaves half an import. The export,
`export_rows()`, writes the same columns back out, guarding any cell that
starts with `=`, `+`, `-` or `@` with an apostrophe so a spreadsheet
won't run it as a formula; the import takes the apostrophe off again, so
an exported file round-trips unchanged.

### Hymns: `library.Hymnal`, `Hymn`, `HymnEntry` and `Tune`

```python
class Hymnal(models.Model):  # a hymn book the church uses, a library entry
    name, short_name ("short code", unique in the church), copies_owned, filing_location, archived

class Hymn(models.Model):  # the text, whichever books print it
    first_line, metre, text, text_credit  # all optional
    suited_use_types, suited_seasons, suited_occasions  # as a score's
    not_same_as = models.ManyToManyField("self", blank=True)

class HymnEntry(models.Model):  # a hymn's number in one hymnal
    hymn = models.ForeignKey(Hymn, on_delete=models.CASCADE, related_name="entries")
    hymnal = models.ForeignKey(Hymnal, on_delete=models.PROTECT, related_name="entries")
    number = models.CharField(max_length=10)  # unique in the hymnal; text, as books have 123a
    tune = models.ForeignKey("Tune", null=True, blank=True, on_delete=models.SET_NULL)  # the book's own

class Tune(models.Model):
    name, metre  # name unique in the church
```

All four belong to a church. Nothing about hymns is bundled with the
app: no lists of hymns, numbers, tunes or texts, so there's no question
of whose index may be reused, and a wrong number can't look
authoritative. The church's hymns build up through use: the first time
someone types NEH 53 into a Hymn slot, `HymnEntry.find_or_make()` makes
the entry and a bare hymn for it, and the first line, words, metre and
tags can be added later from the hymn's page, nudged by a quiet line on
the service until they are.

**A hymn and its entries are different things.** The same text is NEH
53 in one book and another number in the next. A service's piece points
at the entry, because the congregation needs the number that was
chosen, but "last sung" (`HymnQuerySet.with_last_sung()`, the same rule
as scores, with no manual date) and suggestions go by the hymn, so the
same hymn sung from two books counts once. That only works once the two
entries share a hymn, so a hymn whose first line matches another's,
ignoring case and punctuation, asks on its page whether they're the
same. Yes calls `absorb()`, which moves the other's entries across in
one transaction so every service keeps its history; no is remembered in
`not_same_as`, symmetrical, so it isn't asked again. It's never
automatic, as two hymns can begin alike.

**A hymnal is archived, not deleted,** once hymns have been recorded
from it: `HymnEntry.hymnal` is `PROTECT`, and the delete page says to
archive instead. Archived books aren't offered in the forms.

**Numbers sort as a book prints them.** `HymnEntry.number_order()` puts
the leading digits first as a whole number, so 9 comes before 10 and
123a after 123, which plain text sorting gets wrong.

**Metre** belongs to the text, and a tune has its own.
`library/metre.py` writes every metre one way, so "88 88", "8.8.8.8" and
"LM" all become "8.8.8.8", keeping a doubled verse's "D" and lines of
ten or more whole; anything it doesn't recognise, such as "Irregular",
is kept as typed. Both models normalise in `save()`. A match is
necessary for a tune to fit a text but not enough, so the interface
says "same metre", never "fits".

**Tunes have no numbers of their own.** Books print a tune under a
hymn, so a tune's number in a book is derived: `Tune.number_in(hymnal)`
is the lowest number of an entry the book prints with that tune, the
rule chosen for a tune printed twice. That's what lets the pew sheet
print "NEH 53, tune NEH 115", so someone can keep a finger in the
music, falling back to the tune's name when the book doesn't print it.
A service's tune is chosen on the hymn's row once it's in a slot,
from `tune_choices()`: the book's own, then tunes in the same metre the
same book prints, then any other the church knows.

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
    hymns = models.CharField(max_length=200, blank=True)  # no longer shown; see below
    psalm = models.CharField(max_length=100, blank=True)  # no longer shown; see below
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
        as TBC in draft mode. Each row carries its slot's kind and proper
        part. See README §4."""
        ...

    def music_list_groups(self, draft=False, arrangement="service_order"):
        """The rows in one group, or with "propers_beside", the propers
        and then the rest; an empty group is left out."""
        ...
```

**`hymns` and `psalm`, from fields to slots:** these began as plain
text fields, kept apart from the slots because a hymn number didn't
seem to need a shortlist, a confirmation step or a link to
`library.Score`. Once a piece could be a typed reference (see
`RolePiece`), that reasoning went: hymns and psalms can be ordinary
slots, shown, ordered and confirmed like the rest, and the music list
no longer needs an aside for them. Migration `planning/0023` copied
each service's hymns into one Hymns slot, a confirmed reference piece
per comma-separated hymn in the order typed, and the psalm into a Psalm
slot. Confirmed, because that text was what the music list already
printed. The fields themselves stay, still holding the old text, until
a later migration drops them along with `SiteConfig.show_hymns_psalm`,
once the copied slots have been checked on real data.

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
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, blank=True)  # filled from the name when blank
    proper_part = models.CharField(max_length=20, choices=PROPER_PART_CHOICES, blank=True)
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

**Kinds, fixed as a set but free per slot:** `kind` is one of nine
(Proper, Ordinary, Hymn, Psalm, Canticle, Antiphon, Motet, Organ,
Other) and decides how a slot is shown and grouped. `proper_part` says
which proper a slot is (Introit, Gradual and so on), so the day's chant
can one day be found for it. They're separate on purpose: a church that
sings a hymn at the Introit keeps the slot's proper part and changes its
kind to Hymn, so it prints as a hymn. The set of kinds is fixed in
`planning/slot_kinds.py`, but any one slot's kind can be changed; a
label the set lacks, such as Responsory, is Other.

**Classified from the name:** `slot_kinds.classify()` knows the usual
names (Introit, Kyrie, Magnificat) and, failing that, goes by the last
word, so "Communion hymn" is a Hymn and "Opening voluntary" Organ.
`save()` uses it whenever `kind` is blank, so slots from templates, and
slots added with the Kind left as "From the slot's name", classify
themselves. Offertory and Communion on their own are the propers, as in
the Mass template. Migration `planning/0020` classified the slots that
existed before; it keeps its own copy of the table, because a migration
has to give the same result whenever it runs, even after the table in
the app has grown.

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

### Suggestions (`planning/suggestions.py`)

Not a model: what the piece picker's suggestions rest on, worked out
for one service at a time.

- `facts_for(service, window_weeks)` gives every score in the church a
  `ScoreFacts`: the occasion it's tagged for (the service's own or one
  of its other occasions), the season, its use types, when it was last
  sung and whether that's inside the repeat window, and whether it's
  planned for another service later this term. It takes six queries
  however large the library is: the tag tables are read once as sets,
  rather than once per score.
- `placed(facts, use_type)` gives a score's group, its strength (an
  occasion counts more than a season, a season more than a use type)
  and its reasons in plain words. `grouped()` orders a slot's list by
  them for the propose page, and `page_options()` gives the service
  page its one list of scores, in group order before any slot's use
  type is known.
- A slot's use type is the church's use type named like the slot, or
  else like its kind (`slot_use_type()`). It's the only part that
  differs between slots, so the service page still carries the library
  once: `score-picker.js` does that one check per slot, by the same
  rule, and regroups. Its sort is stable, so the server's title order
  holds within each group.

**Ranking, never hiding:** every score stays in the list. A score sung
recently drops below the rest of its group, with its date, instead of
disappearing, because a repeat is sometimes the point.

**Hymns too:** `hymn_suggestions(role, window)` applies the same
`placed()` to hymns, with hymns' own repeat window, for a Hymn slot.
Only suited hymns are offered, a handful at most, as a whole hymnal
would be no help, each under its number in the slot's usual book. On
the service page they're buttons that fill in the book and number; the
propose page lists them as text.

**"Already planned this term"** counts services from today on only. A
score sung earlier this term already shows "Sung 2 weeks ago", so it
isn't flagged twice.

### `planning.RolePiece`

```python
class RolePiece(models.Model):
    service_role = models.ForeignKey(ServiceRole, on_delete=models.CASCADE, related_name="pieces")
    score = models.ForeignKey("library.Score", null=True, blank=True, on_delete=models.PROTECT, related_name="role_pieces")
    hymn_entry = models.ForeignKey("library.HymnEntry", null=True, blank=True, on_delete=models.PROTECT, related_name="role_pieces")
    reference = models.CharField(max_length=200, blank=True)  # e.g. "Psalm 150, tone 4"
    tune = models.ForeignKey("library.Tune", null=True, blank=True, on_delete=models.SET_NULL, related_name="role_pieces")
    is_confirmed = models.BooleanField(default=False)
    comments = GenericRelation("comments.Comment")

    class Meta:
        constraints = [
            models.CheckConstraint(  # exactly one of score, hymn_entry, reference
                condition=..., name="role_piece_one_of_three", violation_error_message=ONE_PIECE_MESSAGE,
            ),
            models.CheckConstraint(  # a tune only for a hymn
                condition=Q(tune__isnull=True) | Q(hymn_entry__isnull=False), name="role_piece_tune_only_for_a_hymn",
            ),
        ]

    @property
    def title(self): ...  # the score, "NEH 53", or the reference as typed
    @property
    def sheet_title(self): ...  # for the pew sheet: "NEH 53, tune NEH 115"
    @property
    def sung_tune(self): ...  # the tune chosen here, or the book's own
    def tune_choices(self): ...  # usual tune, same metre in the book, the rest
```

**A score or a reference:** hymns, psalms and chant are rarely in a
church's library as scores, so a piece can instead be a short typed
reference. Exactly one of the two is set, and the database enforces
it. I first checked the same rule in `clean()` as well, but Django runs
a model's constraints when a form is validated, so an empty form
reported the problem twice, once as "Constraint … is violated". The
message now lives on the constraint, one rule in one place.

**Then a hymn, the third choice:** a piece can also be a hymn, by its
entry in one of the church's hymnals (see `library.Hymn`), so the rule
became exactly one of three. That brought back a check in the form,
for a different reason: Django leaves a constraint out of a form's
validation when it names a field the form doesn't show, and
`hymn_entry` is set from a book and a number rather than shown. So
`RolePieceForm.clean()` says the rule itself, with the same wording as
the constraint, held in one constant, `ONE_PIECE_MESSAGE`. Everything
that shows a piece (the service page, the music list, `__str__` for
comments) prints `title`, so neither kind needs a case of its own.
"Last sung" and the score page's history go from a score to its pieces,
so a reference never reaches them. The propose form asks for the
reference first in Hymn, Psalm and Antiphon slots
(`ServiceRole.takes_reference_first`) and for a score first elsewhere.

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
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)  # empty once they delete their account
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
    music_list_arrangement = models.CharField(max_length=20, choices=ARRANGEMENT_CHOICES, default="service_order")
    repeat_window_weeks = models.PositiveSmallIntegerField(default=8)  # 1 to 104
    hymn_repeat_window_weeks = models.PositiveSmallIntegerField(default=6)  # hymns come round more often
    show_hymns_psalm = models.BooleanField(default=True)  # no longer used; to be dropped

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

**Music list arrangement:** `service_order` prints each service's slots
in order; `propers_beside` prints its propers as a list of their own
beside the rest of its music (`Service.music_list_groups()`). The two
lists sit side by side where the entry is wide enough and one under the
other in a narrow newspaper column or on paper, so neither is squeezed.

**Repeat window:** how recent counts as "sung recently" when pieces are
suggested. It's a setting, not a constant, because a cathedral with a
daily choir and a parish with a monthly sung Mass need different
answers. Eight weeks to start.

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
