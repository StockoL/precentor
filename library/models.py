from django.apps import apps
from django.db import models, transaction
from django.db.models import BooleanField, Case, OuterRef, Q, Subquery, When
from django.db.models.functions import Coalesce, Greatest
from django.urls import reverse
from django.utils import timezone

from accounts.querysets import OrganisationQuerySet

from .validators import tidy_vocal_range, validate_vocal_range

RANGE_FIELDS = ("range_soprano", "range_alto", "range_tenor", "range_bass")


class ScoreQuerySet(OrganisationQuerySet):
    # The Voicing filter's value for "any four-part mixed".
    MIXED = "mixed"
    # The Voicing and Language filters' value for scores without one.
    UNSPECIFIED = "unspecified"

    def search(self, query):
        """
        Every word of the query must match somewhere: in the title, the
        composer's names, the arranger or the editor. An AND across words
        of an OR across fields, so "byrd ave" finds Byrd's Ave verum, not
        every Byrd.
        """
        queryset = self
        for word in query.split():
            queryset = queryset.filter(
                Q(title__icontains=word)
                | Q(composer_surname__icontains=word)
                | Q(composer_other_names__icontains=word)
                | Q(arranger__icontains=word)
                | Q(editor__icontains=word)
            )
        return queryset

    def with_voicing(self, voicing):
        """One voicing exactly, or MIXED: every one of the four parts
        present, so SATB and anything larger, such as SSATB."""
        if voicing == self.MIXED:
            return self.filter(
                soprano_parts__gt=0, alto_parts__gt=0, tenor_parts__gt=0, bass_parts__gt=0
            )
        return self.filter(voicing=voicing)

    # Slot kinds whose music is sung words a pew sheet prints.
    TEXT_KINDS = ["motet", "antiphon"]

    def needing_text(self):
        """Scores with no text that have been planned into a motet or
        antiphon slot, so a pew sheet would want their words. Scores never
        used there, such as Mass settings, aren't counted. The slot is
        reached by name in the lookup, so library still doesn't import
        from planning."""
        return self.filter(text="", role_pieces__service_role__kind__in=self.TEXT_KINDS).distinct()

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
    # Whose library this score is in.
    organisation = models.ForeignKey(
        "accounts.Organisation", on_delete=models.CASCADE, related_name="scores"
    )
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
    # Voicing and language help with planning, but a score is usable
    # without them: only the title and composer are needed.
    voicing = models.CharField(
        max_length=50, blank=True, help_text="As printed, e.g. SATB, SSATB, SATB.SATB"
    )
    # Part counts make voicing filterable without parsing the free text.
    soprano_parts = models.PositiveSmallIntegerField(
        "sopranos",
        default=0,
        help_text="How many parts of each: 2 for SSATB, 0 if none",
    )
    alto_parts = models.PositiveSmallIntegerField("altos", default=0)
    tenor_parts = models.PositiveSmallIntegerField("tenors", default=0)
    bass_parts = models.PositiveSmallIntegerField("basses", default=0)
    language = models.CharField(max_length=50, blank=True, help_text="e.g. Latin, English")
    copies_owned = models.PositiveIntegerField(default=0)
    filing_location = models.CharField(
        max_length=100, blank=True, help_text="Where the copies are kept, e.g. By-01"
    )
    duration_minutes = models.PositiveIntegerField(
        "duration (minutes)", blank=True, null=True
    )
    background = models.TextField(
        blank=True, help_text="Where the piece comes from: its history, text and context."
    )
    notes = models.TextField(
        "interpretation notes",
        blank=True,
        help_text="How you take it: tempo, balance, things to rehearse.",
    )
    # The words sung and a translation, for the pew sheet. Typed by the
    # church: the liturgical Latin is public domain, but many translations
    # aren't, so the credit matters and nothing is filled in for them.
    text = models.TextField(blank=True, help_text="The words as sung, line by line.")
    translation = models.TextField(blank=True)
    translation_credit = models.CharField(
        max_length=200, blank=True, help_text='Who made the translation, e.g. "Tr. Ronald Knox".'
    )
    range_soprano = models.CharField(
        "soprano range",
        max_length=20,
        blank=True,
        validators=[validate_vocal_range],
        help_text="Lowest to highest note, e.g. C4–A5",
    )
    range_alto = models.CharField(
        "alto range", max_length=20, blank=True, validators=[validate_vocal_range]
    )
    range_tenor = models.CharField(
        "tenor range", max_length=20, blank=True, validators=[validate_vocal_range]
    )
    range_bass = models.CharField(
        "bass range", max_length=20, blank=True, validators=[validate_vocal_range]
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
    # The import this score came from, if any; scores added by hand have
    # none. While the import is pending it can be removed as one batch.
    import_batch = models.ForeignKey(
        "ScoreImport", null=True, blank=True, on_delete=models.SET_NULL, related_name="scores"
    )

    objects = ScoreQuerySet.as_manager()

    class Meta:
        # As a library catalogue orders them: by composer, then title.
        # Other names split composers who share a surname (the Bachs).
        ordering = ["composer_surname", "composer_other_names", "title"]  # noqa (Django Meta, not a normal class — no shared-state risk)

    def __str__(self):
        return f"{self.title} ({self.composer})"

    def clean(self):
        """Store vocal ranges in one form ('a3 - e5' becomes 'A3–E5').
        Runs after each field's validators, so the ranges are valid."""
        for field in RANGE_FIELDS:
            setattr(self, field, tidy_vocal_range(getattr(self, field)))

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


class Hymnal(models.Model):
    """
    A hymn book the church uses: a library entry like a score, with its
    copies and where they're kept. Which hymns it holds, and their numbers,
    build up later through use. An archived hymnal is kept for the history
    of what was sung from it, but no longer offered.
    """

    organisation = models.ForeignKey(
        "accounts.Organisation", on_delete=models.CASCADE, related_name="hymnals"
    )
    objects = OrganisationQuerySet.as_manager()
    name = models.CharField(max_length=100, help_text="e.g. New English Hymnal")
    short_name = models.CharField(
        "short code", max_length=20, help_text="As written before a hymn number, e.g. NEH"
    )
    copies_owned = models.PositiveIntegerField(default=0)
    filing_location = models.CharField(max_length=100, blank=True, help_text="Where the copies are kept")
    archived = models.BooleanField(default=False, help_text="No longer used, but kept for its history.")

    class Meta:
        ordering = ["archived", "name"]  # noqa
        constraints = [  # noqa
            # One NEH per church: the code is how a hymn number is read.
            models.UniqueConstraint(
                fields=["organisation", "short_name"], name="hymnal_short_name_unique_per_organisation"
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.short_name})"


class Hymn(models.Model):
    """
    A hymn as a text, whichever books print it, so singing NEH 53 and then
    the same hymn from another book counts as singing it twice. Hymns build
    up through use: one is made the first time a book and number is typed,
    and its first line can be added whenever someone knows it.
    """

    organisation = models.ForeignKey(
        "accounts.Organisation", on_delete=models.CASCADE, related_name="hymns"
    )
    objects = OrganisationQuerySet.as_manager()
    first_line = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return self.first_line or "A hymn with no first line yet"


class HymnEntry(models.Model):
    """
    Where a hymn appears: its number in one hymnal. A service's hymn points
    here, not at the hymn, as the congregation needs the book and number
    that was chosen. The number is text, as books have 123a and appendices.
    """

    organisation = models.ForeignKey(
        "accounts.Organisation", on_delete=models.CASCADE, related_name="hymn_entries"
    )
    objects = OrganisationQuerySet.as_manager()
    hymn = models.ForeignKey(Hymn, on_delete=models.CASCADE, related_name="entries")
    # A hymnal with entries can't be deleted, only archived: what was sung
    # from it is history worth keeping.
    hymnal = models.ForeignKey(Hymnal, on_delete=models.PROTECT, related_name="entries")
    number = models.CharField(max_length=10)

    class Meta:
        ordering = ["hymnal", "number"]  # noqa
        constraints = [  # noqa
            models.UniqueConstraint(fields=["hymnal", "number"], name="hymn_entry_number_unique_in_hymnal"),
        ]

    def __str__(self):
        """"NEH 53", as it's written in a service."""
        return f"{self.hymnal.short_name} {self.number}"

    @classmethod
    def find_or_make(cls, hymnal, number):
        """The entry for this number in this hymnal, made along with a new
        hymn the first time it's used."""
        number = number.strip()
        entry = cls.objects.filter(hymnal=hymnal, number__iexact=number).first()
        if entry is None:
            hymn = Hymn.objects.create(organisation_id=hymnal.organisation_id)
            entry = cls.objects.create(
                organisation_id=hymnal.organisation_id, hymn=hymn, hymnal=hymnal, number=number
            )
        return entry


class ScoreImport(models.Model):
    """
    One spreadsheet imported into a church's library. Its scores are
    ordinary scores from the start, but while the import is pending it can
    be removed as a whole, in case the file wasn't what was meant. Keeping
    it ends that: the scores stay as they are, and from then on are only
    deleted one by one.
    """

    PENDING, KEPT = "pending", "kept"

    organisation = models.ForeignKey(
        "accounts.Organisation", on_delete=models.CASCADE, related_name="score_imports"
    )
    objects = OrganisationQuerySet.as_manager()
    created_by = models.ForeignKey(
        "accounts.User", null=True, on_delete=models.SET_NULL, related_name="score_imports"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    original_filename = models.CharField(max_length=255)
    status = models.CharField(max_length=10, choices=[(PENDING, "Pending"), (KEPT, "Kept")], default=PENDING)
    # What the result page reports: rows skipped and why, likely duplicates,
    # and whether the file had to be read as an older Excel encoding.
    report = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]  # noqa

    @property
    def is_pending(self):
        return self.status == self.PENDING

    def keep(self):
        """Close the batch for good: its scores are ordinary scores now."""
        self.status = self.KEPT
        self.save(update_fields=["status"])

    @transaction.atomic
    def remove(self):
        """
        Delete the batch's scores and then the batch, all or nothing. A
        score already planned into a service is protected, so it's kept
        and just unlinked from the batch. Returns (deleted, kept_in_use).
        Only a pending batch can be removed.
        """
        if not self.is_pending:
            raise ValueError("A kept import can't be removed as a batch.")
        in_use = self.scores.filter(role_pieces__isnull=False).distinct()
        kept_in_use = in_use.count()
        in_use.update(import_batch=None)
        deleted = self.scores.count()
        self.scores.all().delete()
        self.delete()
        return deleted, kept_in_use

    def __str__(self):
        return f"{self.original_filename} ({self.created_at:%d %b %Y})"
