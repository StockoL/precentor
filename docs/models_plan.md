# Precentor — App Breakdown & Model Plan

This document translates the [ERD](erd.mmd) into a concrete Django app
structure and field-level model plan, ahead of scaffolding the project.
See the main [README](../README.md) for the reasoning behind each
domain concept.

## App breakdown

| App        | Owns                                                                      | Rationale                                                                                    |
| ---------- | ------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| `accounts` | User profile/role (conductor vs. librarian)                               | Keeps auth/permissions separate from domain logic                                            |
| `library`  | `Score`, plus copies/filing fields                                        | The reusable "what do we own" side, independent of any term                                  |
| `ordo`     | `LiturgicalOccasion` (season/tradition logic, moveable feast calculation) | Self-contained calendar engine; conceivably reusable elsewhere                               |
| `planning` | `Term`, `Service`, `ServiceRole`, `RolePiece`                             | The core planning workflow — the spine of the MVP                                            |
| `comments` | `Comment` (generic relation via `contenttypes`)                           | Cuts across `planning`, so it's cleanest as its own app rather than living inside `planning` |

Dependency direction is deliberately one-way: `planning` imports from
`library` and `ordo`, never the reverse. This avoids circular imports
and keeps the "spine" app easy to reason about and test in isolation.

## Model field plan

### `library.Score`

```python
class Score(models.Model):
    title = models.CharField(max_length=200)
    composer = models.CharField(max_length=200)
    arranger = models.CharField(max_length=200, blank=True)
    voicing = models.CharField(max_length=50)  # free text, e.g. "SATB", "SSATB", "SATB.SATB"
    soprano_parts = models.PositiveSmallIntegerField(default=0)
    alto_parts = models.PositiveSmallIntegerField(default=0)
    tenor_parts = models.PositiveSmallIntegerField(default=0)
    bass_parts = models.PositiveSmallIntegerField(default=0)
    language = models.CharField(max_length=50)
    lead_time_tag = models.CharField(max_length=50, blank=True)
    copies_owned = models.PositiveIntegerField(default=0)
    filing_location = models.CharField(max_length=100, blank=True)
    duration_minutes = models.PositiveIntegerField(blank=True, null=True)
    suited_use_types = models.ManyToManyField("ordo.UseType", blank=True, related_name="suited_scores")
    suited_seasons = models.ManyToManyField("ordo.LiturgicalSeason", blank=True, related_name="suited_scores")
    suited_occasions = models.ManyToManyField("ordo.LiturgicalOccasion", blank=True, related_name="suited_scores")
```

**Three-tier suitability tagging, ranking not filtering:** `suited_use_types` / `suited_seasons` / `suited_occasions` are three genuinely distinct kinds of fact (a service's structural type, a broad calendar season, a specific named day), not one generic tag concept. `Score.objects` uses a custom `ScoreQuerySet.ranked_by_suitability(occasion=, season=, use_type=)` that annotates an `is_suited` flag and sorts matching scores to the top — it never filters, since an untagged score might still be the right choice and the tool shouldn't claim to know otherwise.

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
    comments = GenericRelation("comments.Comment")

    class Meta:
        ordering = ["date"]

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

**`GenericRelation` on the commentable models:** `Term`, `Service`, and `RolePiece` each carry a `comments = GenericRelation("comments.Comment")` field. This adds no database column and needs no migration — it's a query-time convenience (enabling `term.comments.all()`) that also makes Django cascade-delete a target's comments if the target itself is deleted, completing the `GenericForeignKey` relationship properly per Django's own recommended pattern. This technically means `planning` now references `comments`, a justified exception to the one-way dependency rule above, since `comments.models.Comment` still has zero knowledge of `planning`'s models in return.

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
