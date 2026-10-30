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

from library.models import Score

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
    in_term: bool = False  # already proposed or confirmed elsewhere this term

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
    in_term = set(
        RolePiece.objects.filter(service_role__service__term_id=service.term_id, score__isnull=False)
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
