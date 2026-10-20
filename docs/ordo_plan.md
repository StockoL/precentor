# Precentor: Ordo Calendar Features

A design document: the reasoning I worked out and wrote down before
writing the code. It covers two related but separable features that
put the computus algorithm and the `ordo` app to real use, instead of
leaving them as correct machinery that hardly anything calls.

> **Update, 19 October 2026: Catholic only.** Both features were first
> designed for two traditions (Catholic and Church of England), chosen
> per term. I've since narrowed Precentor to the Roman calendar: the
> `tradition` field is gone from `LiturgicalSeason`,
> `LiturgicalOccasion`, `Term` and `Service`, along with
> `effective_tradition()`, and `occasion_for_date()` now takes only a
> date and a calendar use. `calendar_use` stays, relabelled as the
> Ordinary Form and the 1962 Extraordinary Form. The reasoning is in
> the README's out-of-scope list. The code samples below show the
> current shape; the reasoning around them is unchanged.

---

## 1. Problem statement

`LiturgicalOccasion.date_for_year(year)`, built on the tested computus
algorithm, only answered one question: "given an occasion I already
know, what date does it fall on this year?" That's only useful once a
conductor has already picked the occasion from a dropdown. Nothing in
the app asked the more useful reverse question: "given a date, which
occasion is it?" And `Score.suited_occasions`, the feature `ordo` was
originally built for in my earliest MoSCoW list, hadn't been
implemented. Two features close both gaps:

1. **Occasion suggestions** when creating or editing a service, based
   on its date.
2. **Suitability tagging** on scores: repertoire suited to a season or
   occasion, brought forward when proposing pieces.

---

## 2. Feature 1: occasion suggestions

### Settled

- A reverse lookup that checks a date against every named
  `LiturgicalOccasion`'s `date_for_year(year)`:

```python
def occasion_for_date(target_date, calendar_use):
    candidates = LiturgicalOccasion.objects.filter(calendar_use=calendar_use)
    return [
        occasion
        for occasion in candidates
        if occasion.date_for_year(target_date.year) == target_date
    ]
```

It returns a list, because more than one occasion can fall on a date
(see "Multiple matching occasions" below).

- This is lighter than, and different from, an idea I'd already
  dropped: modelling seasons as continuous date ranges. The lookup only
  checks the named occasions that have been entered, and never claims
  to know about a day nobody entered.
- It's a suggestion, never enforced. The conductor can always choose
  something else or ignore it.

### Calendar use: term default, service override

I settled this from how churches actually work. Most use one calendar
throughout, but some (Catholic oratories with both EF and NO Masses,
for example) need to override it for single services within a term.

`LiturgicalOccasion` records the calendar it belongs to:

```python
CALENDAR_USE_CHOICES = [
    ("current", "Ordinary Form (Novus Ordo)"),
    ("historic", "Extraordinary Form (1962)"),
]
calendar_use = models.CharField(max_length=20, choices=CALENDAR_USE_CHOICES, default="current")
```

`Term.calendar_use` is **required**, which covers the usual case of a
single calendar. `Service.calendar_use` is **optional**
(`null=True, blank=True`), set only when one service differs from its
term. A model method, following the same convention as
`Service.status`, resolves "the override if set, otherwise the term's"
in one place:

```python
def effective_calendar_use(self):
    return self.calendar_use or self.term.calendar_use
```

That answers which calendar the lookup runs against:
`occasion_for_date(date, service.effective_calendar_use())`.

**Not covered by this:** entering real Extraordinary Form occasions is
still a separate, large content task, as it was when I first raised
it. This settles how the calendar is chosen, nothing more; in practice
only calendars with real data behind them are worth choosing.

### Multiple matching occasions: offered as choices

When more than one occasion matches a date, the form offers them all.
The conductor may attach one, several or none; the app doesn't pick
one silently or encode rules of precedence.

**Only an additive model change:** `Service.occasion` stays as it is, a
single foreign key for the _main_ occasion, which drives the occasion
colour accents already built, with no change to that working code. A
new, separate field holds any others:

```python
additional_occasions = models.ManyToManyField(
    "ordo.LiturgicalOccasion", blank=True, related_name="also_relevant_services"
)
```

I chose this over turning `occasion` itself into a many-to-many, which
would have meant revisiting and re-testing everything that reads
`service.occasion` as a single value.

**A side note on lectionary cycles:** the EF's one-year cycle and the
Ordinary Form's three-year lectionary (Years A, B and C) don't make
`ordo`'s job any harder. The lectionary cycle decides which _readings_
belong to a Sunday that already has a name and a date, and `ordo`
never models readings (see the README's scope boundary). The EF may
still be quicker to enter, for a different reason: it's long settled,
with nothing new being added, whereas the Ordinary Form keeps gaining
optional memorials. That's a smaller dataset, not a simpler structure.

### Mechanism: a live suggestion in JavaScript

Settled: a live suggestion fetched with `fetch()` whenever the date
changes, in keeping with the confirm and comment interactions already
built, over a simpler version that reloads the page.

---

## 3. Feature 2: suitability tagging on scores

- `Score.suited_occasions = models.ManyToManyField("ordo.LiturgicalOccasion", blank=True, related_name="suited_scores")`
- Added to `ScoreForm`.
- The library list takes `suited_occasion`, `suited_season` and
  `suited_use_type` in the query string, alongside the existing
  search and filters.
- The propose-piece picker on `service_detail.html` puts the pieces
  suited to the service first. That's where the feature pays off: the
  library leans towards the right music when proposing, instead of
  showing everything in title order.

### Three tiers, not one generic tag

These are three different things, and I didn't merge them into one
generic tag. That's unlike comments, which use a single
`GenericForeignKey`: comments are the _same_ relationship to different
kinds of target, whereas these are three _different_ kinds of fact
that happen to serve the same purpose.

1. **Use type:** a property of the service itself (Mass, Vespers,
   General use), independent of the calendar.
2. **Season:** a broad part of the calendar (Advent, Christmas,
   Lent and so on).
3. **Specific occasion:** a single named day (Advent Sunday 4, the
   Seventh Sunday in Ordinary Time, SS Peter & Paul).

```python
class UseType(models.Model):
    name = models.CharField(max_length=50)

class LiturgicalSeason(models.Model):
    name = models.CharField(max_length=50)
```

`Score` gains three separate many-to-many fields: `suited_use_types`,
`suited_seasons` and `suited_occasions`.

**This needs one more field:** for the tiers to connect, so that a
piece tagged "suitable for Advent" comes forward for a service on
"Advent Sunday 4", `LiturgicalOccasion` needs
`season = models.ForeignKey(LiturgicalSeason, null=True, blank=True,
on_delete=models.SET_NULL)`. Without it, a season tag and a day tag
never meet.

### Untagged scores: ranking, not filtering

Removing untagged scores from the results would be a mistake: they
might still be the right choice, and the app has no way of knowing
otherwise. So the query doesn't use
`Score.objects.filter(suited_occasions=...)`, which would hide
everything untagged. It's an **annotated sort** instead: every score
stays in the results, and those matching the service's occasion,
season or use type move to the top.

My first version joined through the tags, which listed a score with
several tags once for each tag. The version I built,
`ScoreQuerySet.ranked_by_suitability()`, asks of each tier whether the
score is among those tagged with it, so each score appears once:

```python
conditions = []
if occasion is not None:
    tagged = Score.objects.filter(suited_occasions=occasion).values("pk")
    conditions.append(When(pk__in=tagged, then=True))
# ... the same for season and use_type

return self.annotate(
    is_suited=Case(*conditions, default=False, output_field=BooleanField())
).order_by("-is_suited", "title")
```
