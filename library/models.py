from django.db import models
from django.db.models import BooleanField, Case, When
from django.urls import reverse


class ScoreQuerySet(models.QuerySet):
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

        conditions = []
        if occasion is not None:
            conditions.append(When(suited_occasions=occasion, then=True))
        if season is not None:
            conditions.append(When(suited_seasons=season, then=True))
        if use_type is not None:
            conditions.append(When(suited_use_types=use_type, then=True))

        return (
            self.annotate(
                is_suited=Case(*conditions, default=False, output_field=BooleanField())
            )
            .order_by("-is_suited", "title")
            .distinct()
        )


class Score(models.Model):
    title = models.CharField(max_length=200)
    composer_surname = models.CharField(max_length=100)
    composer_other_names = models.CharField(max_length=100, blank=True)
    arranger = models.CharField(max_length=200, blank=True)
    voicing = models.CharField(
        max_length=50
    )  # free text, e.g. "SATB", "SSATB", "SATB.SATB"
    soprano_parts = models.PositiveSmallIntegerField(default=0)
    alto_parts = models.PositiveSmallIntegerField(default=0)
    tenor_parts = models.PositiveSmallIntegerField(default=0)
    bass_parts = models.PositiveSmallIntegerField(default=0)
    language = models.CharField(max_length=50)
    copies_owned = models.PositiveIntegerField(default=0)
    filing_location = models.CharField(max_length=100, blank=True)
    duration_minutes = models.PositiveIntegerField(blank=True, null=True)
    suited_use_types = models.ManyToManyField(
        "ordo.UseType",
        blank=True,
        related_name="suited_scores",
        help_text="e.g. Eucharist, General use, Evening, Harvest",
    )
    suited_seasons = models.ManyToManyField(
        "ordo.LiturgicalSeason",
        blank=True,
        related_name="suited_scores",
        help_text="e.g. Advent, Christmas, Lent, Easter, Trinity",
    )
    suited_occasions = models.ManyToManyField(
        "ordo.LiturgicalOccasion",
        blank=True,
        related_name="suited_scores",
        help_text="Specific named days, e.g. Advent Sunday 4, Trinity 7",
    )

    objects = ScoreQuerySet.as_manager()

    class Meta:
        ordering = ["title"]  # noqa (Django Meta, not a normal class — no shared-state risk)

    def __str__(self):
        return f"{self.title} ({self.composer})"

    @property
    def composer(self):
        if self.composer_other_names:
            return f"{self.composer_other_names} {self.composer_surname}"
        return self.composer_surname

    def get_absolute_url(self):
        return reverse("library:score_detail", kwargs={"pk": self.pk})
