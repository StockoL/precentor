"""
Suggesting scores for a service's slots. Every score in the church's
library is offered, never hidden: suggestions only reorder the list and
say why. What a suggestion rests on is worked out once per service, in a
fixed number of queries however large the library; the one thing that
differs from slot to slot is the slot's use type.
"""

from dataclasses import dataclass, field
from datetime import timedelta

from django.utils import timezone
from django.utils.timesince import timesince

from library.models import Hymn, Score
from ordo.models import UseType

from .models import RolePiece


@dataclass
class ScoreFacts:
    """What's known about one score for one service."""

    score: Score
    occasion: str = ""  # the matching occasion's name, if tagged for one
    season: str = ""  # the season's name, if tagged for it
    use_type_ids: set = field(default_factory=set)
    last_sung: object = None  # a date, or None if never sung
    recent: bool = False  # sung within the church's repeat window
    in_term: bool = False  # planned for another service later this term

    @property
    def sung_text(self):
        """"Sung 2 weeks ago" inside the window, "Last sung 14 months ago"
        outside it, nothing if it's never been sung."""
        if self.last_sung is None:
            return ""
        ago = timesince(self.last_sung, timezone.localdate(), depth=1)
        return f"Sung {ago} ago" if self.recent else f"Last sung {ago} ago"


def facts_for(service, window_weeks):
    """Every score in the service's church, in title order, with its facts."""
    occasions = [o for o in [service.occasion, *service.additional_occasions.all()] if o]
    season = service.occasion.season if service.occasion else None
    scores = list(Score.objects.for_organisation(service.organisation_id).with_last_sung().order_by("title"))

    # One query each for the tags that matter, rather than one per score.
    occasion_names = {o.pk: str(o) for o in occasions}
    tagged_occasion = {}
    for score_id, occasion_id in Score.suited_occasions.through.objects.filter(
        liturgicaloccasion_id__in=occasion_names
    ).values_list("score_id", "liturgicaloccasion_id"):
        tagged_occasion.setdefault(score_id, occasion_names[occasion_id])
    tagged_season = set(
        season.suited_scores.filter(organisation_id=service.organisation_id).values_list("pk", flat=True)
    ) if season else set()
    use_types = {}
    for score_id, use_type_id in Score.suited_use_types.through.objects.filter(
        score__organisation_id=service.organisation_id
    ).values_list("score_id", "usetype_id"):
        use_types.setdefault(score_id, set()).add(use_type_id)
    # Planned for another service from today on: one already sung shows
    # its date instead, so it isn't flagged twice.
    in_term = set(
        RolePiece.objects.filter(
            service_role__service__term_id=service.term_id,
            service_role__service__date__gte=timezone.localdate(),
            score__isnull=False,
        )
        .exclude(service_role__service=service)
        .values_list("score_id", flat=True)
    )

    since = timezone.localdate() - timedelta(weeks=window_weeks)
    return [
        ScoreFacts(
            score=score,
            occasion=tagged_occasion.get(score.pk, ""),
            season=season.name if score.pk in tagged_season else "",
            use_type_ids=use_types.get(score.pk, set()),
            last_sung=score.last_sung,
            recent=score.last_sung is not None and score.last_sung > since,
            in_term=score.pk in in_term,
        )
        for score in scores
    ]


# The groups a slot's list is shown in, in order. Nothing is left out:
# scores sung recently still appear, below the rest of their group.
GROUPS = [
    ("suggested", "Suggested"),
    ("suggested_recent", "Suggested, sung recently"),
    ("other", "Other scores"),
    ("other_recent", "Other scores, sung recently"),
]


def slot_use_type(slot, use_types):
    """The church's use type named like the slot ("Communion"), or else
    like its kind ("Motet"), or None. A convenience, not a rule."""
    by_name = {use_type.name.casefold(): use_type for use_type in use_types}
    return by_name.get(slot.role_name.casefold()) or by_name.get(slot.get_kind_display().casefold())


def placed(facts, use_type=None):
    """
    Where a score goes in a slot's list, and why: its group, how strongly
    it's suited (an occasion counts more than a season, a season more than
    a use type), and its reasons in plain words.
    """
    for_use = use_type is not None and use_type.pk in facts.use_type_ids
    strength = (bool(facts.occasion), bool(facts.season), for_use)
    reasons = [f"For {name}" for name in (facts.occasion, facts.season) if name]
    if for_use:
        reasons.append(f"For {use_type.name}")
    if facts.sung_text:
        reasons.append(facts.sung_text)
    if facts.in_term:
        reasons.append("Already planned this term")
    group = ("suggested" if any(strength) else "other") + ("_recent" if facts.recent else "")
    return group, strength, reasons


def grouped(all_facts, use_type=None):
    """A slot's list as [(label, [(score, reasons), ...]), ...], each group
    strongest first and then by title, empty groups left out."""
    groups = {key: [] for key, _ in GROUPS}
    for facts in all_facts:
        group, strength, reasons = placed(facts, use_type)
        groups[group].append((strength, facts.score, reasons))
    return [
        (label, [(score, reasons) for _, score, reasons in sorted(
            groups[key], key=lambda entry: (tuple(not part for part in entry[0]), entry[1].title)
        )])
        for key, label in GROUPS if groups[key]
    ]


def page_options(service, window_weeks):
    """
    The service page's one list of scores, for every slot's search box:
    each score's facts, in group order before any slot's use type is
    known. score-picker.js adds the slot's use type and regroups; its
    sort is stable, so this order holds within each group.
    """
    def order(facts):
        group, strength, _ = placed(facts)
        return [key for key, _ in GROUPS].index(group), tuple(not part for part in strength)

    return [
        {
            "value": str(facts.score.pk),
            "label": str(facts.score),
            "occasion": facts.occasion,
            "season": facts.season,
            "useTypes": sorted(facts.use_type_ids),
            "sung": facts.sung_text,
            "recent": facts.recent,
            "inTerm": facts.in_term,
        }
        for facts in sorted(facts_for(service, window_weeks), key=order)
    ]


def hymn_suggestions(role, window_weeks, limit=8):
    """
    The hymns to suggest for a Hymn slot, by the same rules as scores but
    with hymns' own repeat window: each as its number in the slot's usual
    book where it has one, with its reasons. Only hymns tagged for the
    day, the season or the slot's use are suggested, at most a handful,
    as a whole hymnal would be no help; hymns sung recently come last.
    """
    service = role.service
    hymnals = role.hymnals_on_offer
    if not hymnals:
        return []
    occasion_names = {o.pk: str(o) for o in [service.occasion, *service.additional_occasions.all()] if o}
    season = service.occasion.season if service.occasion else None
    use_type = slot_use_type(role, UseType.objects.for_organisation(service.organisation_id))
    hymns = (
        Hymn.objects.for_organisation(service.organisation_id)
        .with_last_sung()
        .prefetch_related("entries__hymnal", "suited_occasions", "suited_seasons", "suited_use_types")
    )
    in_term = set(
        RolePiece.objects.filter(
            service_role__service__term_id=service.term_id,
            service_role__service__date__gte=timezone.localdate(),
            hymn_entry__isnull=False,
        )
        .exclude(service_role__service=service)
        .values_list("hymn_entry__hymn_id", flat=True)
    )
    since = timezone.localdate() - timedelta(weeks=window_weeks)
    order = [key for key, _ in GROUPS]
    found = []
    for hymn in hymns:
        entries = [entry for entry in hymn.entries.all() if entry.hymnal in hymnals]
        if not entries:
            continue
        entry = next((e for e in entries if e.hymnal == role.default_hymnal), entries[0])
        # The same facts as a score's, about a hymn; the entry is what's offered.
        facts = ScoreFacts(
            score=entry,
            occasion=next((occasion_names[o.pk] for o in hymn.suited_occasions.all() if o.pk in occasion_names), ""),
            season=season.name if season and season in hymn.suited_seasons.all() else "",
            use_type_ids={use.pk for use in hymn.suited_use_types.all()},
            last_sung=hymn.last_sung,
            recent=hymn.last_sung is not None and hymn.last_sung > since,
            in_term=hymn.pk in in_term,
        )
        group, strength, reasons = placed(facts, use_type)
        if group.startswith("suggested"):
            found.append((order.index(group), tuple(not part for part in strength), str(entry), entry, reasons))
    found.sort(key=lambda item: item[:3])
    return [(entry, reasons) for *_, entry, reasons in found[:limit]]
