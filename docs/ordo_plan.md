# Precentor — Ordo Calendar Features: Design Document

A design/planning document: reasoning worked out and written down
before code is written. Covers two related but separable features that
give the existing computus algorithm/`Ordo` work a genuine payoff, rather
than leaving it as correct-but-underused machinery.

---

## 1. Problem statement

`LiturgicalOccasion.date_for_year(year)` (built on the tested computus
algorithm) currently only answers "given a specific, already-known
occasion, what date does it fall on this year" — which only gets used
when a conductor already knows which occasion to pick from a dropdown.
Nothing in the app currently asks the more useful reverse question:
"given a date, what occasion is this?" And `Score.suited_occasions` —
the feature `Ordo` for which it was originally built, per the project's
own earliest MoSCoW — has not been implemented. Two features close both gaps:

1. **Occasion auto-suggest** when creating/editing a Service, based on
   its date.
2. **`Score.suited_occasions`** tagging and filtering — repertoire
   suitable for a season/occasion, surfaced when proposing pieces.

---

## 2. Feature 1: Occasion auto-suggest

### Confirmed

- A reverse-lookup function, checking a candidate date against every
  named `LiturgicalOccasion`'s `date_for_year(year)`:

```python
def occasion_for_date(target_date, tradition):
    for occasion in LiturgicalOccasion.objects.filter(tradition=tradition):
        if occasion.date_for_year(target_date.year) == target_date:
            return occasion
    return None
```

- This is deliberately lighter than, and different from, a
  previously-descoped idea of modelling continuous season date-ranges — it
  only ever checks against specific, already-modelled named occasions, never
  invents coverage for days for which nothing was entered.
- Suggestion, never silent enforcement — the conductor can always
  override or ignore it.

### Open questions

### Tradition/calendar-use selection: Term default, Service override

Resolved via real usage patterns rather than a hypothetical: most
churches use one tradition/calendar throughout, but some (e.g.
Catholic oratories running both EF and NO Masses) need per-service
override within the same term.

`LiturgicalOccasion` gains a second axis:

```python
CALENDAR_USE_CHOICES = [
    ("current", "Current (Common Worship / Novus Ordo)"),
    ("historic", "Historic (Book of Common Prayer / Extraordinary Form)"),
]
calendar_use = models.CharField(max_length=20, choices=CALENDAR_USE_CHOICES, default="current")
```

`Term` gets both fields **required** (the sensible default for the
common single-tradition case). `Service` gets both fields **optional**
(`null=True, blank=True`) — set only when a specific service genuinely
differs from its term. A fat-model helper (matching `Service.status`'s
own convention) resolves "override if set, else inherit from Term" in
one place:

```python
def effective_tradition(self):
    return self.tradition or self.term.tradition

def effective_calendar_use(self):
    return self.calendar_use or self.term.calendar_use
```

This directly answers the "which tradition does the lookup run against" question:

`occasion_for_date(date, service.effective_tradition(),
service.effective_calendar_use())`.

**Explicitly not committed to by this:** populating real Extraordinary
Form or Book of Common Prayer occasion data remains a separate, large
content task, unchanged from when it was first raised in planning. This
resolves the _selection mechanism_ only — the model cleanly supports all four
combinations; only whichever ones have real data behind them need to
be usable in practice.

### Multiple matching occasions: present as choices, additive model change only

When more than one occasion matches a date, present both
as options — the conductor may attach one, or both, or neither - not have
the system silently pick or encode precedence rules.

**Structural consequence, resolved to be purely additive:** `Service.
occasion` stays exactly as it is — a single FK, the _primary_ occasion,
driving the already-built accent bar/badge/dot without any changes to
that working code. A new, separate field holds anything else relevant:

```python
additional_occasions = models.ManyToManyField(
    "ordo.LiturgicalOccasion", blank=True, related_name="also_relevant_services"
)
```

This was deliberately chosen over converting `occasion` itself to a
many-to-many, which would have required revisiting and re-testing
every already-built piece that currently reads `service.occasion` as a
single value.

**Aside, worth a brief clarification:** the EF calendar's 1-year cycle
vs. Novus Ordo/Common Worship's 3-year lectionary cycle (Year A/B/C)
doesn't actually add complexity to `Ordo`'s own job — the lectionary
cycle governs which _readings_ are assigned to an already-named,
already-dated Sunday, and `Ordo` deliberately never models readings at
all (see the README's scope boundary). Where EF may genuinely be
simpler to enter is a different, real reason: it's long-stable with no
ongoing modern additions, versus Common Worship's more actively
expanding set of optional commemorations — a smaller dataset, not a
structurally simpler one.

### Mechanism: live JS suggestion

Confirmed: a live `fetch()`-based suggestion as the date field changes,
consistent with the confirm-toggle/comment interactions already built,
over a simpler reload-based alternative.

---

## 3. Feature 2: `Score.suited_occasions`

- `Score.suited_occasions = models.ManyToManyField("ordo.LiturgicalOccasion", blank=True, related_name="suited_scores")`
- Added to `ScoreForm`.
- `ScoreListView.get_queryset()` gains a `suited_for` filter param,
  following the existing voicing/language `GET`-param filtering
  pattern.
- The propose-piece picker on `service_detail.html` can default-filter
  to "suited for this service's occasion" — the actual payoff moment:
  the library narrows to appropriate music automatically when
  proposing, rather than showing everything.

### Three-tier suitability, not one generic tag

Confirmed as three genuinely distinct things, not unified into one
generic tag concept (unlike the comment `GenericForeignKey`
unification — those were the _same_ relationship to different target
types; these are three _different_ kinds of fact that happen to serve
the same filtering goal):

1. **Use-type** — a structural property of the service itself
   (Eucharist / Evening / General), independent of the calendar.
2. **Season** — a broad calendar category (Advent, Christmas, Lent...).
3. **Specific occasion** — an individual named day (Advent Sunday 4,
   Trinity 7, SS Peter & Paul).

```python
class UseType(models.Model):
    name = models.CharField(max_length=50)

class LiturgicalSeason(models.Model):
    name = models.CharField(max_length=50)
    tradition = models.CharField(max_length=20, choices=LiturgicalOccasion.TRADITION_CHOICES)
```

`Score` gains three separate M2M fields:
`suited_use_types`, `suited_seasons`, `suited_occasions` (the last
already planned).

**A necessary addition this implies, not optional:** for the tiers to
actually connect — so a piece tagged broadly "suitable for Advent"
gets surfaced for a service specifically on "Advent Sunday 4" —
`LiturgicalOccasion` needs `season = models.ForeignKey(LiturgicalSeason,
null=True, blank=True, on_delete=models.SET_NULL)`. Without it, a
season-level tag and a day-level tag never meet.

### Untagged scores: ranking, not filtering

Removing untagged scores from results entirely would be a
real mistake — they might still be relevant, and the tool shouldn't
claim to know otherwise. This changes the actual mechanism: rather
than `Score.objects.filter(suited_occasions=...)` (which would hide
everything untagged), the query becomes an **annotated sort** — every
score stays in the results; ones matching the current service's
occasion, season, or use-type are bubbled to the top:

```python
from django.db.models import Case, When, BooleanField

scores = Score.objects.annotate(
    is_suited=Case(
        When(suited_occasions=service.occasion, then=True),
        When(suited_seasons=service.occasion.season, then=True),
        When(suited_use_types__name__iexact=service_use_type, then=True),
        default=False,
        output_field=BooleanField(),
    )
).order_by("-is_suited", "title")
```
