from django.apps import apps
from django.db import models
from django.db.models import BooleanField, Case, OuterRef, Subquery, When
from django.db.models.functions import Coalesce, Greatest
from django.urls import reverse
from django.utils import timezone


class ScoreQuerySet(models.QuerySet):
    def with_last_sung(self):
        """
        Annotate each score with last_sung: the latest date it was sung.

        Derived, never stored. "Sung" means a confirmed piece in a service
        dated on or before today; a confirmed piece in a future service is
        scheduled, not sung. The manual date covers history from before
        Precentor, and whichever date is later wins.

        A Subquery rather than a Max() over a join, so it stays correct
        when combined with ranked_by_suitability's joins. RolePiece is
        looked up by name because library mustn't import from planning.
        """
        RolePiece = apps.get_model("planning", "RolePiece")
        latest_confirmed = (
            RolePiece.objects.filter(
                score=OuterRef("pk"),
                is_confirmed=True,
                service_role__service__date__lte=timezone.localdate(),
            )
            .order_by("-service_role__service__date")
            .values("service_role__service__date")[:1]
        )
        return self.annotate(
            last_sung_recorded=Subquery(latest_confirmed),
            # Greatest of a date and NULL is NULL on SQLite but the date on
            # PostgreSQL; coalescing each side gives the same answer on both.
            last_sung=Greatest(
                Coalesce("last_sung_recorded", "last_sung_manual"),
                Coalesce("last_sung_manual", "last_sung_recorded"),
            ),
        )

    def ranked_by_suitability(self, occasion=None, season=None, use_type=None):
        """
        Ranking, not filtering — every score stays in the results;
        scores matching any of the three suitability tiers (occasion,
        season, use-type) for the given context are bubbled to the top.
        Untagged scores are never hidden, since they might still be
        relevant and the tool shouldn't claim to know otherwise.
        """
        if not (occasion or season or use_type):
            return self.order_by("title")

        # Each condition asks "is this score among those tagged X?" as a
        # subquery. Joining through the tags instead gave a score with
        # several tags one row per tag, some suited and some not, so it
        # appeared more than once.
        conditions = []
        if occasion is not None:
            tagged = Score.objects.filter(suited_occasions=occasion).values("pk")
            conditions.append(When(pk__in=tagged, then=True))
        if season is not None:
            tagged = Score.objects.filter(suited_seasons=season).values("pk")
            conditions.append(When(pk__in=tagged, then=True))
        if use_type is not None:
            tagged = Score.objects.filter(suited_use_types=use_type).values("pk")
            conditions.append(When(pk__in=tagged, then=True))

        return self.annotate(
            is_suited=Case(*conditions, default=False, output_field=BooleanField())
        ).order_by("-is_suited", "title")


class Score(models.Model):
    title = models.CharField(max_length=200)
    composer_surname = models.CharField(
        max_length=100, help_text="Used for sorting, e.g. Palestrina"
    )
    composer_other_names = models.CharField(
        "composer's other names",
        max_length=100,
        blank=True,
        help_text="Forenames and any particle, e.g. Giovanni Pierluigi da",
    )
    arranger = models.CharField(max_length=200, blank=True)
    # Separate from arranger: an arranger changes the music, an editor
    # prepares an edition of it.
    editor = models.CharField(
        max_length=200, blank=True, help_text="Of this edition, e.g. Stockton"
    )
    voicing = models.CharField(
        max_length=50, help_text="As printed, e.g. SATB, SSATB, SATB.SATB"
    )
    # Part counts make voicing filterable without parsing the free text.
    soprano_parts = models.PositiveSmallIntegerField(
        "sopranos",
        default=0,
        help_text="Number of soprano parts, e.g. 2 for SSATB (0 if none)",
    )
    alto_parts = models.PositiveSmallIntegerField(
        "altos", default=0, help_text="Number of alto parts (0 if none)"
    )
    tenor_parts = models.PositiveSmallIntegerField(
        "tenors", default=0, help_text="Number of tenor parts (0 if none)"
    )
    bass_parts = models.PositiveSmallIntegerField(
        "basses", default=0, help_text="Number of bass parts (0 if none)"
    )
    language = models.CharField(max_length=50, help_text="e.g. Latin, English")
    copies_owned = models.PositiveIntegerField(default=0)
    filing_location = models.CharField(
        max_length=100, blank=True, help_text="Where the copies are kept, e.g. By-01"
    )
    duration_minutes = models.PositiveIntegerField(
        "duration (minutes)", blank=True, null=True
    )
    # "Last sung" is derived from confirmed pieces in past services (see
    # ScoreQuerySet.with_last_sung). This is only for history from before
    # Precentor; the library shows whichever date is later.
    last_sung_manual = models.DateField(
        "last sung (before Precentor)",
        blank=True,
        null=True,
        help_text="Only for history before Precentor. Later services are recorded automatically.",
    )
    suited_use_types = models.ManyToManyField(
        "ordo.UseType",
        verbose_name="suitable uses",
        blank=True,
        related_name="suited_scores",
        help_text="e.g. Mass, Vespers, General use",
    )
    suited_seasons = models.ManyToManyField(
        "ordo.LiturgicalSeason",
        verbose_name="suitable seasons",
        blank=True,
        related_name="suited_scores",
        help_text="e.g. Advent, Christmas, Lent, Easter, Ordinary Time",
    )
    suited_occasions = models.ManyToManyField(
        "ordo.LiturgicalOccasion",
        verbose_name="suitable occasions",
        blank=True,
        related_name="suited_scores",
        help_text="Specific named days, e.g. Fourth Sunday of Advent, Corpus Christi",
    )

    objects = ScoreQuerySet.as_manager()

    class Meta:
        # As a library catalogue orders them: by composer, then title.
        # Other names split composers who share a surname (the Bachs).
        ordering = ["composer_surname", "composer_other_names", "title"]  # noqa (Django Meta, not a normal class — no shared-state risk)

    def __str__(self):
        return f"{self.title} ({self.composer})"

    @property
    def composer(self):
        if self.composer_other_names:
            return f"{self.composer_other_names} {self.composer_surname}"
        return self.composer_surname

    @property
    def composer_catalogue(self):
        """
        The composer as a library catalogue lists them, surname first,
        with any arranger and editor in brackets:
        "Palestrina, Giovanni Pierluigi da (ed. Stockton)".
        """
        name = self.composer_surname
        if self.composer_other_names:
            name = f"{name}, {self.composer_other_names}"
        credits = []
        if self.arranger:
            credits.append(f"arr. {self.arranger}")
        if self.editor:
            credits.append(f"ed. {self.editor}")
        if credits:
            name = f"{name} ({'; '.join(credits)})"
        return name

    def get_absolute_url(self):
        return reverse("library:score_detail", kwargs={"pk": self.pk})
