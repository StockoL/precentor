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
