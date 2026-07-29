# Precentor — App Breakdown & Model Plan

This document translates the [ERD](erd.mmd) into a concrete Django app
structure and field-level model plan, ahead of scaffolding the project.
See the main [README](../README.md) for the reasoning behind each
domain concept.

## App breakdown

| App        | Owns                                                                      | Rationale                                                                                    |
| ---------- | ------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| `accounts` | User profile/role (conductor vs. librarian), `ConductorRequiredMixin`     | Keeps auth/permissions separate from domain logic; the mixin lives here so any app can gate a view by role without depending on `planning` |
| `library`  | `Score`, plus copies/filing fields                                        | The reusable "what do we own" side, independent of any term                                  |
| `ordo`     | `LiturgicalOccasion` (season/tradition logic, moveable feast calculation) | Self-contained calendar engine; conceivably reusable elsewhere                               |
| `planning` | `Term`, `Service`, `TermMarker`, `ServiceRole`, `RolePiece`               | The core planning workflow — the spine of the MVP                                            |
| `comments` | `Comment` (generic relation via `contenttypes`)                           | Cuts across `planning`, so it's cleanest as its own app rather than living inside `planning` |
| `core`     | `SiteConfig` (church name, crest, house colour, layout toggles)           | Site-wide branding/print-layout preferences, not owned by any one term — doesn't belong inside `planning` |

Dependency direction is deliberately one-way: `planning` imports from
`accounts`, `library`, `ordo`, and `core`, never the reverse. This
avoids circular imports and keeps the "spine" app easy to reason about
and test in isolation. `core` also imports `ConductorRequiredMixin`
from `accounts` — it needed the same conductor-only gate as `planning`
for its settings page, which is exactly why the mixin was moved out of
`planning` and into `accounts` rather than duplicated.

## Model field plan

### `library.Score`

```python
class Score(models.Model):
    title = models.CharField(max_length=200)
    composer_surname = models.CharField(max_length=100)
    composer_other_names = models.CharField(max_length=100, blank=True)
    arranger = models.CharField(max_length=200, blank=True)
    voicing = models.CharField(max_length=50)  # free text, e.g. "SATB", "SSATB", "SATB.SATB"
    soprano_parts = models.PositiveSmallIntegerField(default=0)
    alto_parts = models.PositiveSmallIntegerField(default=0)
    tenor_parts = models.PositiveSmallIntegerField(default=0)
    bass_parts = models.PositiveSmallIntegerField(default=0)
    language = models.CharField(max_length=50)
    copies_owned = models.PositiveIntegerField(default=0)
    filing_location = models.CharField(max_length=100, blank=True)
    duration_minutes = models.PositiveIntegerField(blank=True, null=True)
    suited_use_types = models.ManyToManyField("ordo.UseType", blank=True, related_name="suited_scores")
    suited_seasons = models.ManyToManyField("ordo.LiturgicalSeason", blank=True, related_name="suited_scores")
    suited_occasions = models.ManyToManyField("ordo.LiturgicalOccasion", blank=True, related_name="suited_scores")

    @property
    def composer(self):
        """"{other_names} {surname}", or just the surname if no other
        names were given — the display form used everywhere else."""
        ...
```

**Composer split, surname required:** `composer` was originally one free-text field; it's now `composer_surname` (required) and `composer_other_names` (optional), so cataloguing/searching by surname alone always works even when a full name isn't known. `composer` lives on as a read-only property for display and `__str__`, not a database column — admin `search_fields` and any filtering must target the two real fields instead.

**`lead_time_tag` removed:** dropped as unnecessary micromanagement — the field added a rehearsal-scheduling axis nothing else in the app used or surfaced.

**Three-tier suitability tagging, ranking not filtering:** `suited_use_types` / `suited_seasons` / `suited_occasions` are three genuinely distinct kinds of fact (a service's structural type, a broad calendar season, a specific named day), not one generic tag concept. `Score.objects` uses a custom `ScoreQuerySet.ranked_by_suitability(occasion=, season=, use_type=)` that annotates an `is_suited` flag and sorts matching scores to the top — it never filters, since an untagged score might still be the right choice and the tool shouldn't claim to know otherwise. Each field carries `help_text` with examples (e.g. "Eucharist, General use, Evening, Harvest") since the underlying `UseType`/`LiturgicalSeason` vocab is otherwise invisible until populated — `ordo`'s `0004_seed_use_types_and_seasons` data migration seeds a starter set of both (real `LiturgicalOccasion` data remains the separate, larger content task noted below).

**Voicing design decision:** an earlier version of this plan used a fixed
`choices` list for `voicing` (SATB, SATTB, unison, etc.). This was
dropped because real voicing notation isn't a small closed set — it's a
compact notation with combinatorial possibilities (SSATB, SATB.SATB for
double choir, and so on), which a fixed dropdown can't represent
faithfully. Instead, `voicing` is kept as free text for accurate
human-readable display, while `soprano_parts` / `alto_parts` /
`tenor_parts` / `bass_parts` hold the actual part _counts_, enabling
reliable filtering (e.g. "needs a tenor at all" or "exactly SSATB")
without parsing free text.

**Deliberately out of scope:** precise double-choir modelling (e.g.
distinguishing which parts belong to which of two choirs). The part
counts describe a single choir's texture; double-choir pieces are
recorded accurately in the free-text `voicing` field only. This is
flagged in the README as a scope limit, not an oversight.

### `ordo.LiturgicalOccasion`

```python
COLOUR_CHOICES = [
    ("violet", "Violet"),
    ("red", "Red"),
    ("green", "Green"),
    ("white", "White/Gold"),
    ("rose", "Rose"),
]

CALENDAR_USE_CHOICES = [
    ("current", "Current (Common Worship / Novus Ordo)"),
    ("historic", "Historic (Book of Common Prayer / Extraordinary Form)"),
]

TRADITION_CHOICES = [("catholic", "Catholic"), ("cofe", "Church of England")]

class LiturgicalSeason(models.Model):
    name = models.CharField(max_length=50)
    tradition = models.CharField(max_length=20, choices=TRADITION_CHOICES)

class UseType(models.Model):
    name = models.CharField(max_length=50)

class LiturgicalOccasion(models.Model):
    TRADITION_CHOICES = TRADITION_CHOICES
    name = models.CharField(max_length=100)
    tradition = models.CharField(max_length=20, choices=TRADITION_CHOICES)
    calendar_use = models.CharField(max_length=20, choices=CALENDAR_USE_CHOICES, default="current")
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


def occasion_for_date(target_date, tradition, calendar_use):
    """Reverse lookup: which LiturgicalOccasion(s) fall on target_date.
    Scopes candidates by tradition/calendar_use, then evaluates
    date_for_year() in Python since it isn't a database column. Returns
    a list — zero, one, or more occasions can share a date."""
    ...
```

**Fixed-date design decision:** the original plan used a single `fixed_date = DateField()` for non-moveable occasions. This was wrong — a `DateField` stores one specific year's date, but Christmas Day recurs on the same month/day every year. Replaced with `fixed_month`/`fixed_day`, mirroring how moveable occasions already work via `easter_offset_days` — both resolve to an actual date only when `date_for_year(year)` is called, never stored as a fixed year.

**Colour design decision — the mirror image of the voicing decision above:** liturgical colour is a genuinely small, fixed, real-world vocabulary (violet/red/green/white/rose) — unlike voicing's combinatorial notation problem, there's no equivalent of "SATB.SATB" here needing free text. `choices` was added specifically so every stored value maps predictably onto a CSS design token name (see `docs/design_system.md`), rather than risking a typo like `"Purple"` vs `"violet"` silently breaking that mapping.

**Deliberately out of scope:** Ordo is strictly a naming/dating/colour-tagging engine for repertoire filtering and service labelling — it does not model readings, psalms, propers, or rubrical detail (e.g. whether the Gloria is said), regardless of how many calendar traditions it eventually covers. See the README's out-of-scope list.

**Tradition vs. calendar-use, and the reverse lookup:** `calendar_use` is a second, independent axis from `tradition` — some traditions (e.g. Catholic oratories) run both a `current` and a `historic` calendar side by side. `LiturgicalSeason` and `UseType` exist to support three-tier `Score` suitability tagging (see below); `LiturgicalOccasion.season` is the link that lets a season-level tag (e.g. "Advent") and a day-level tag (e.g. "Advent Sunday 4") match each other. `occasion_for_date()` is the reverse of `date_for_year()` — given a date, which occasion(s) is it — used to auto-suggest a `Service`'s occasion from its date.

### `planning.Term`

```python
class Term(models.Model):
    name = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    tradition = models.CharField(max_length=20, choices=TRADITION_CHOICES)
    calendar_use = models.CharField(max_length=20, choices=CALENDAR_USE_CHOICES)
    comments = GenericRelation("comments.Comment")

    class Meta:
        ordering = ["start_date"]

    def get_absolute_url(self):
        ...

    def completion_summary(self):
        """Aggregates Service.status counts across this term's services,
        for the dashboard/landing view. See README §3.3."""
        ...
```

### `planning.Service`

```python
class Service(models.Model):
    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name="services")
    date = models.DateField()
    service_type = models.CharField(max_length=50)  # e.g. "sung_eucharist"
    occasion = models.ForeignKey(
        "ordo.LiturgicalOccasion", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="services",
    )
    additional_occasions = models.ManyToManyField(
        "ordo.LiturgicalOccasion", blank=True, related_name="also_relevant_services",
    )
    tradition = models.CharField(max_length=20, choices=TRADITION_CHOICES, null=True, blank=True)
    calendar_use = models.CharField(max_length=20, choices=CALENDAR_USE_CHOICES, null=True, blank=True)
    hymns = models.CharField(max_length=200, blank=True)
    psalm = models.CharField(max_length=100, blank=True)
    comments = GenericRelation("comments.Comment")

    class Meta:
        ordering = ["date"]

    def effective_tradition(self):
        return self.tradition or self.term.tradition

    def effective_calendar_use(self):
        return self.calendar_use or self.term.calendar_use

    @property
    def status(self):
        """Derived, not stored: not_started / in_progress / complete."""
        ...

    def music_list_rows(self, draft=False):
        """Rows for music list rendering — N/A roles always skipped;
        unconfirmed roles skipped in the public version, shown as TBC
        in draft mode. See README §4."""
        ...
```

**`hymns`/`psalm` as plain fields, not roles:** these were always
intended as simple text/reference fields, separate from the
Score-driven roles (`ServiceRole`/`RolePiece`) that model
Setting/Anthem-type slots — a hymn number or psalm reference doesn't
need a shortlist, a confirmation step, or a link to `library.Score`.

**`GenericRelation` on the commentable models:** `Term`, `Service`, and `RolePiece` each carry a `comments = GenericRelation("comments.Comment")` field. This adds no database column and needs no migration — it's a query-time convenience (enabling `term.comments.all()`) that also makes Django cascade-delete a target's comments if the target itself is deleted, completing the `GenericForeignKey` relationship properly per Django's own recommended pattern. This technically means `planning` now references `comments`, a justified exception to the one-way dependency rule above, since `comments.models.Comment` still has zero knowledge of `planning`'s models in return.

### `planning.TermMarker`

```python
class TermMarker(models.Model):
    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name="markers")
    date = models.DateField()
    text = models.CharField(max_length=200)

    class Meta:
        ordering = ["date"]
```

Lets a conductor drop a one-off free-text note at a specific date in a
term's timeline — half-term, a retreat, anything that isn't itself a
Service — for the public music list (see README §4). The music list
view merges `Term.services` and `Term.markers` into a single
date-ordered sequence, tagging each item with its type so the template
can branch on how to render it; there was no existing precedent in the
codebase for merging two querysets like this, so it's built fresh
rather than reusing another feature's merge logic.

### `planning.ServiceRole`

```python
class ServiceRole(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="roles")
    role_name = models.CharField(max_length=50)  # e.g. "Anthem", "Setting"
    is_not_applicable = models.BooleanField(default=False)
```

### `planning.RolePiece`

```python
class RolePiece(models.Model):
    service_role = models.ForeignKey(ServiceRole, on_delete=models.CASCADE, related_name="pieces")
    score = models.ForeignKey("library.Score", on_delete=models.PROTECT, related_name="role_pieces")
    is_confirmed = models.BooleanField(default=False)
    comments = GenericRelation("comments.Comment")
```

### `comments.Comment`

```python
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

class Comment(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    body = models.TextField()
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
    church_name = models.CharField(max_length=200, blank=True)
    crest_image = models.ImageField(upload_to="site_config/", blank=True)
    house_accent_colour = models.CharField(max_length=7, default="#8b1a2b")
    layout_style = models.CharField(max_length=20, choices=LAYOUT_STYLE_CHOICES, default="columns")
    show_hymns_psalm = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        self.pk = 1  # enforce singleton regardless of how it's constructed
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass  # singleton row is never deleted

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
```

**Hand-rolled singleton, no new dependency:** a site only ever has one
of these, so `pk` is pinned to `1` on every save and `get_solo()` is
the one accessor every view uses — the same effect as a package like
`django-solo` would give, without adding a dependency for something
this small.

**`crest_image` is the project's first uploaded file.** Nothing else
in the app stores user-uploaded media, so this needed genuinely new
infrastructure that no other model could reuse: `Pillow` as a
dependency, `MEDIA_ROOT`/`MEDIA_URL` in settings, and dev-time media
serving in the project urlconf. Uploads are validated and normalised
server-side (format/resolution checks, then a centre-crop/resize to a
fixed 4:1 banner slot) by a small `core/imaging.py` helper, called from
`SiteConfigForm.clean_crest_image` rather than from `Model.save()`, so
a bad upload surfaces as an ordinary form error. A hand-rolled
in-browser crop tool (`crest-crop.js`) sits in front of this as
progressive enhancement — pan/zoom onto a canvas, then hand the
cropped result to the same server-side validation — but the server-side
step is what actually guarantees a consistent result, since it also
has to cope with the plain, uncropped upload a no-JS visitor submits.

## Template organisation

Templates are kept **per-app** (e.g. `library/templates/library/`) rather
than centralized under one project-level `templates/` folder, so each
app remains self-contained — its templates travel with it, consistent
with the one-way dependency structure above. The single exception is
`templates/base.html` at the project root, which is intentionally
shared across every app rather than owned by any one of them.

## Decisions worth remembering when writing the real code

- `RolePiece.score` uses `on_delete=models.PROTECT` — a Score can't be
  deleted while it's still referenced in planning history, since "last
  sung" history depends on it.
- `Service.status` is a `@property`, computed on the fly rather than
  stored — this keeps it honestly "derived," per the design decision in
  the README (§3.3), and avoids a stored field silently going stale.
- `ServiceRole.is_not_applicable` being `True` counts as an active,
  deliberate decision (equivalent to confirmation) for the purposes of
  `Service.status` — not an absence of data.
- `ScoreDeleteView` catches `ProtectedError` (raised by `RolePiece.score`'s
  `on_delete=PROTECT`) and shows a friendly message rather than an
  unhandled 500 — discovered as a real gap during the visual design
  pass, not anticipated up front.
- `Term.deletion` is intentionally _not_ given the same protection —
  `Service.term` uses `on_delete=CASCADE`, so deleting a term correctly
  takes its whole planning history with it, a deliberately different
  choice from `RolePiece.score`.
- `Comment` deletion is only permitted while `is_open` is `False` —
  enforced server-side in `comments.views.delete_comment`, not just by
  hiding the button — so a comment can't be silently discarded while
  still an open query. Deleting a parent cascades to its replies via
  the existing `on_delete=CASCADE` on `Comment.parent`.
- `Term.tradition`/`calendar_use` are required (the common single-tradition
  case); `Service.tradition`/`calendar_use` are optional overrides, resolved
  by `effective_tradition()`/`effective_calendar_use()`. This supports
  churches that run more than one calendar within the same term (e.g.
  Catholic oratories running both EF and NO Masses) without forcing every
  church to set an override.
- `Service.occasion` stays a single FK — driving the accent bar/badge/dot
  exactly as before. `Service.additional_occasions` is a separate,
  purely additive M2M for the case where more than one occasion
  genuinely matches a date; this was chosen over converting `occasion`
  itself to a many-to-many, which would have required re-testing every
  already-built piece that reads `service.occasion` as a single value.
  The public music list now also renders it — a second occasion is
  shown as a stacked secondary label alongside the primary one, rather
  than replacing it.
- `ConductorRequiredMixin` lives in `accounts`, not `planning` — it
  checks user/group membership, nothing term- or service-specific, and
  `core`'s settings page needed the same conductor-only gate. Moving it
  once avoided either duplicating the check or making `core` depend on
  `planning` for something that was never really `planning`'s to own.
- `SiteConfig.layout_style` only changes the **public** music list.
  Draft mode always renders the plain single-column list regardless of
  that setting, since draft is for a conductor to quickly scan what's
  still TBC, not to preview the final printed shape.
