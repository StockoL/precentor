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
    voicing = models.CharField(max_length=20, choices=VOICING_CHOICES)
    language = models.CharField(max_length=50)
    lead_time_tag = models.CharField(max_length=50, blank=True)
    copies_owned = models.PositiveIntegerField(default=0)
    filing_location = models.CharField(max_length=100, blank=True)
    duration_minutes = models.PositiveIntegerField(blank=True, null=True)
    suited_occasions = models.ManyToManyField(
        "ordo.LiturgicalOccasion", blank=True, related_name="suited_scores"
    )
```

### `ordo.LiturgicalOccasion`

```python
class LiturgicalOccasion(models.Model):
    TRADITION_CHOICES = [("catholic", "Catholic"), ("cofe", "Church of England")]
    name = models.CharField(max_length=100)
    tradition = models.CharField(max_length=20, choices=TRADITION_CHOICES)
    is_moveable = models.BooleanField(default=False)
    fixed_date = models.DateField(blank=True, null=True)       # if not moveable
    easter_offset_days = models.IntegerField(blank=True, null=True)  # if moveable
    colour = models.CharField(max_length=20, blank=True)
```

### `planning.Term`

```python
class Term(models.Model):
    name = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()

    class Meta:
        ordering = ["start_date"]
```

### `planning.Service`

```python
class Service(models.Model):
    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name="services")
    date = models.DateField()
    service_type = models.CharField(max_length=50)  # e.g. "sung_eucharist"
    occasion = models.ForeignKey(
        "ordo.LiturgicalOccasion", on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        ordering = ["date"]

    @property
    def status(self):
        """Derived, not stored: not_started / in_progress / complete."""
        ...
```

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
