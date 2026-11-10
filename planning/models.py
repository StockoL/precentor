from django.apps import apps
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.functional import cached_property

from accounts.querysets import OrganisationQuerySet
from library.models import Hymnal, HymnEntry, Score, Tune
from ordo.models import CALENDAR_USE_CHOICES, proper_chants, weekday_sunday

from .slot_kinds import KIND_CHOICES, MANY_CHANT_KINDS, PROPER_PART_CHOICES, REFERENCE_FIRST, classify


def comment_count_on(model, pks):
    """
    How many comments are attached to the given objects of one model.
    Comments link through a generic relation, so this filters on the
    content type and the ids: one query per model, not one per object.
    """
    Comment = apps.get_model("comments", "Comment")
    return Comment.objects.filter(
        content_type=ContentType.objects.get_for_model(model), object_id__in=pks
    ).count()


class Term(models.Model):
    # Whose term this is.
    organisation = models.ForeignKey(
        "accounts.Organisation", on_delete=models.CASCADE, related_name="terms"
    )
    objects = OrganisationQuerySet.as_manager()
    name = models.CharField(max_length=100, help_text="e.g. Michaelmas 2026")
    start_date = models.DateField()
    end_date = models.DateField()
    calendar_use = models.CharField(
        "calendar",
        max_length=20,
        choices=CALENDAR_USE_CHOICES,
        help_text="Which calendar of the Roman Rite this term follows. "
        "A service can override it.",
    )
    comments = GenericRelation("comments.Comment")

    def completion_summary(self):
        """
        Aggregate service statuses for this term, for dashboard display.
        Reuses Service.status rather than re-deriving anything.
        """
        statuses = [service.status for service in self.services.all()]
        return {
            "total": len(statuses),
            "complete": statuses.count("complete"),
            "in_progress": statuses.count("in_progress"),
            "not_started": statuses.count("not_started"),
        }

    PHASE_LABELS = {  # noqa
        "current": "Current",
        "upcoming": "Upcoming",
        "past": "Past",
    }

    def phase(self, today=None):
        """Where the term sits relative to today: current, upcoming or
        past. today is a parameter so tests can fix the date."""
        today = today or timezone.localdate()
        if today < self.start_date:
            return "upcoming"
        if today > self.end_date:
            return "past"
        return "current"

    def phase_label(self, today=None):
        return self.PHASE_LABELS[self.phase(today)]

    def timing_label(self, today=None):
        """
        "Week 4 of 12" while the term runs, counting from its first day
        with a part week at the end counted as a week; "Starts in 3 weeks"
        (or days) before it; "Ended Fri 25 Dec 2026" after.
        """
        today = today or timezone.localdate()
        phase = self.phase(today)
        if phase == "current":
            week = (today - self.start_date).days // 7 + 1
            weeks = -(-((self.end_date - self.start_date).days + 1) // 7)  # rounds up
            return f"Week {week} of {weeks}"
        if phase == "upcoming":
            days = (self.start_date - today).days
            if days == 1:
                return "Starts tomorrow"
            if days < 14:
                return f"Starts in {days} days"
            return f"Starts in {days // 7} weeks"
        return f"Ended {date_format(self.end_date)}"

    def deletion_summary(self):
        """
        What deleting this term takes with it, for the confirmation page:
        (count, noun) pairs, leaving out anything there's none of.
        """
        service_pks = list(self.services.values_list("pk", flat=True))
        piece_pks = list(
            RolePiece.objects.filter(service_role__service__term=self).values_list(
                "pk", flat=True
            )
        )
        counts = [
            (len(service_pks), "service"),
            (ServiceRole.objects.filter(service__term=self).count(), "slot"),
            (len(piece_pks), "proposed piece"),
            (self.markers.count(), "notice"),
            (
                self.comments.count()
                + comment_count_on(Service, service_pks)
                + comment_count_on(RolePiece, piece_pks),
                "comment",
            ),
        ]
        return [(count, noun) for count, noun in counts if count]

    class Meta:
        ordering = ["start_date"]  # noqa

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("planning:term_detail", kwargs={"pk": self.pk})


class Service(models.Model):
    # Display labels for the derived status. The raw values stay in use
    # for CSS classes (badge--not_started) and comparisons; only the
    # label is shown to people.
    STATUS_LABELS = {  # noqa
        "not_started": "Not started",
        "in_progress": "In progress",
        "complete": "Complete",
    }

    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name="services")
    # Always its term's organisation, copied in save(), so it can be
    # scoped like everything else without anyone having to set it.
    organisation = models.ForeignKey(
        "accounts.Organisation", on_delete=models.CASCADE, related_name="services"
    )
    objects = OrganisationQuerySet.as_manager()
    date = models.DateField()
    service_type = models.CharField(max_length=50, help_text="e.g. Sung Mass, Vespers")
    occasion = models.ForeignKey(
        "ordo.LiturgicalOccasion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="services",
        help_text="The main liturgical day; it sets the service's colour.",
    )
    additional_occasions = models.ManyToManyField(
        "ordo.LiturgicalOccasion",
        verbose_name="other occasions",
        blank=True,
        related_name="also_relevant_services",
        help_text="Any other days this service also marks.",
    )
    calendar_use = models.CharField(
        "calendar",
        max_length=20,
        choices=CALENDAR_USE_CHOICES,
        null=True,
        blank=True,
        help_text="Leave blank to follow the term's calendar.",
    )
    hymns = models.CharField(
        max_length=200, blank=True, help_text="Hymn numbers, e.g. 123, 345, 234"
    )
    psalm = models.CharField(max_length=100, blank=True, help_text="e.g. 150")
    # The template the slots came from, so a second template asks before
    # replacing them. String reference: SlotTemplate is defined below.
    slot_template = models.ForeignKey(
        "SlotTemplate", null=True, blank=True, on_delete=models.SET_NULL, related_name="services"
    )
    comments = GenericRelation("comments.Comment")

    class Meta:
        ordering = ["date"]  # noqa

    def __str__(self):
        return f"{self.service_type} — {date_format(self.date)}"

    def get_absolute_url(self):
        return reverse("planning:service_detail", kwargs={"pk": self.pk})

    def save(self, *args, **kwargs):
        self.organisation_id = self.term.organisation_id
        super().save(*args, **kwargs)

    def effective_calendar_use(self):
        return self.calendar_use or self.term.calendar_use

    @cached_property
    def proper_chants(self):
        """The names of the chants of this day's Mass, {part: [incipits]},
        worked out once for all its slots. An Ordinary Form weekday with no
        occasion sings the Sunday before's; otherwise it's empty without one."""
        from core.models import SiteConfig

        occasion = self.occasion
        if occasion is None and self.effective_calendar_use() == "current":
            occasion = weekday_sunday(self.date, SiteConfig.national_calendar_of(self.organisation_id))
        return proper_chants(occasion, self.date)

    @cached_property
    def references_proposed(self):
        """The typed references already proposed in this service, grouped by
        their slot's (kind, proper part), from one query for all its slots."""
        proposed = {}
        rows = RolePiece.objects.filter(service_role__service=self).exclude(reference="").values_list(
            "service_role__kind", "service_role__proper_part", "reference"
        )
        for kind, part, reference in rows:
            proposed.setdefault((kind, part), set()).add(reference)
        return proposed

    def asks_before_using(self, template):
        """Using another template replaces the slots, so the conductor is
        asked first: whenever there are slots and they didn't come from
        this template."""
        return self.slot_template_id != template.pk and self.roles.exists()

    def use_template(self, template, replace=False):
        """
        Give this service a template's slots. With replace, the current
        slots go first, except any with pieces proposed, which are kept so
        no planning is lost. Returns a dict of slot names: added,
        already_there, removed and kept.
        """
        removed, kept = [], []
        if replace:
            for role in self.roles.prefetch_related("pieces"):
                if role.pieces.all():
                    kept.append(role.role_name)
                else:
                    removed.append(role.role_name)
                    role.delete()
        added, already_there = template.apply_to(self)
        self.slot_template = template
        self.save(update_fields=["slot_template"])
        return {"added": added, "already_there": already_there, "removed": removed, "kept": kept}

    def move_slot(self, role, step):
        """Move one slot up (step -1) or down (+1); at either end, nothing
        happens."""
        roles = list(self.roles.all())
        here = next(i for i, r in enumerate(roles) if r.pk == role.pk)
        there = here + step
        if 0 <= there < len(roles):
            roles[here], roles[there] = roles[there], roles[here]
            self._number_slots(roles)

    def set_slot_order(self, pks):
        """Put the slots in this order (a list of their ids, as after a
        drag). It must name each of this service's slots exactly once."""
        roles = {r.pk: r for r in self.roles.all()}
        if sorted(pks) != sorted(roles):
            raise ValueError("The order must list each of this service's slots once.")
        self._number_slots([roles[pk] for pk in pks])

    @staticmethod
    def _number_slots(roles):
        for number, role in enumerate(roles, start=1):
            if role.position != number:
                role.position = number
                role.save(update_fields=["position"])

    def suggested_scores(self):
        """
        Every score in the church's library, with those suited to this
        service's occasion or its season first. Ranked, never filtered:
        see ScoreQuerySet.ranked_by_suitability.
        """
        occasion = self.occasion
        return Score.objects.for_organisation(self.organisation_id).ranked_by_suitability(
            occasion=occasion, season=occasion.season if occasion else None
        )

    def deletion_summary(self):
        """What deleting this service takes with it; see Term's version."""
        piece_pks = list(
            RolePiece.objects.filter(service_role__service=self).values_list(
                "pk", flat=True
            )
        )
        counts = [
            (self.roles.count(), "slot"),
            (len(piece_pks), "proposed piece"),
            (self.comments.count() + comment_count_on(RolePiece, piece_pks), "comment"),
        ]
        return [(count, noun) for count, noun in counts if count]

    @property
    def status(self):
        """
        Derived, never stored: not_started / in_progress / complete.
        A role counts as "resolved" if it's marked N/A, or if it has
        at least one confirmed piece.
        """
        # .all() and plain Python, not .exists()/.filter()/.count(): those
        # always query, but .all() uses prefetched roles and pieces when a
        # view has loaded them (prefetch_related("roles__pieces")), so a
        # list of services can show every status without a query each.
        roles = list(self.roles.all())
        if not roles:
            return "not_started"

        resolved_count = sum(role.is_resolved for role in roles)
        has_any_piece = any(list(role.pieces.all()) for role in roles)

        if resolved_count == len(roles):
            return "complete"
        if resolved_count == 0 and not has_any_piece:
            return "not_started"
        return "in_progress"

    @property
    def unsettled_slots(self):
        """Names of the slots still to settle (not marked not needed, no
        confirmed piece). Uses .all(), so prefetched slots cost nothing."""
        return [role.role_name for role in self.roles.all() if not role.is_resolved]

    @property
    def status_label(self):
        """The status as shown in the UI, e.g. "Not started". Status is
        derived, not a choices field, so there's no get_status_display()."""
        return self.STATUS_LABELS[self.status]

    def music_list_rows(self, draft=False):
        """The slots to print, in order, with their kind and proper part so
        the music list can arrange and style them, and the titles of their
        confirmed pieces. A draft also lists slots with nothing confirmed."""
        rows = []
        for role in self.roles.all():
            if role.is_not_applicable:
                continue
            confirmed = [p.title for p in role.pieces.all() if p.is_confirmed]
            if not confirmed and not draft:
                continue
            rows.append({
                "role_name": role.role_name,
                "kind": role.kind,
                "proper_part": role.proper_part,
                "pieces": confirmed,
            })
        return rows

    def music_list_groups(self, draft=False, arrangement="service_order"):
        """The music list rows in groups, each printed as a list of its
        own: all of them in service order, or with "propers_beside", the
        propers and then the rest. An empty group is left out."""
        rows = self.music_list_rows(draft=draft)
        if arrangement != "propers_beside":
            return [rows] if rows else []
        propers = [row for row in rows if row["kind"] == "proper"]
        rest = [row for row in rows if row["kind"] != "proper"]
        return [group for group in (propers, rest) if group]

    def pew_sheet_rows(self):
        """The slots to print for the congregation: each that has a
        confirmed piece, in order, with the pieces themselves, as a score's
        text and composer may be printed too. Uses .all(), so prefetched
        slots and pieces cost nothing."""
        rows = []
        for role in self.roles.all():
            confirmed = [piece for piece in role.pieces.all() if piece.is_confirmed]
            if confirmed and not role.is_not_applicable:
                rows.append({"role_name": role.role_name, "kind": role.kind, "pieces": confirmed})
        return rows


class TermMarker(models.Model):
    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name="markers")
    # Always its term's organisation, copied in save(), so it can be
    # scoped like everything else without anyone having to set it.
    organisation = models.ForeignKey(
        "accounts.Organisation", on_delete=models.CASCADE, related_name="markers"
    )
    objects = OrganisationQuerySet.as_manager()
    date = models.DateField()
    # "Notice" is the UI word for a TermMarker.
    text = models.CharField("notice", max_length=200)

    class Meta:
        ordering = ["date"]  # noqa

    def save(self, *args, **kwargs):
        self.organisation_id = self.term.organisation_id
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.text} ({date_format(self.date)})"


class ServiceRole(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="roles")
    # Always its service's organisation, copied in save().
    organisation = models.ForeignKey(
        "accounts.Organisation", on_delete=models.CASCADE, related_name="service_roles"
    )
    objects = OrganisationQuerySet.as_manager()
    # "Slot" is the UI word for a ServiceRole.
    KINDS = KIND_CHOICES  # for the Kind select on each slot
    role_name = models.CharField("slot", max_length=50)
    # What it holds, for showing and grouping it, and for a proper, which
    # one. Left blank, save() works both out from the name.
    kind = models.CharField(
        max_length=10, choices=KIND_CHOICES, blank=True,
        help_text="Leave it to be worked out from the slot's name.",
    )
    proper_part = models.CharField(max_length=20, choices=PROPER_PART_CHOICES, blank=True)
    is_not_applicable = models.BooleanField("not needed (N/A)", default=False)
    # The slot's place in the service; a new slot goes at the end, and the
    # conductor can move it (Move up and Move down, or drag).
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]  # noqa

    def save(self, *args, **kwargs):
        self.organisation_id = self.service.organisation_id
        if not self.kind:
            self.kind, self.proper_part = classify(self.role_name)
        if self._state.adding and not self.position:
            last = self.service.roles.aggregate(models.Max("position"))["position__max"]
            self.position = (last or 0) + 1
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.role_name} ({self.service})"

    def deletion_summary(self):
        """What removing this slot takes with it; see Term's version."""
        piece_pks = list(self.pieces.values_list("pk", flat=True))
        counts = [
            (len(piece_pks), "proposed piece"),
            (comment_count_on(RolePiece, piece_pks), "comment"),
        ]
        return [(count, noun) for count, noun in counts if count]

    @cached_property
    def hymnals_on_offer(self):
        """The church's hymnals in use, for a Hymn slot's book and number.
        Any other kind of slot takes a score or a reference instead."""
        if self.kind != "hymn":
            return []
        return list(Hymnal.objects.for_organisation(self.organisation_id).filter(archived=False))

    @cached_property
    def default_hymnal(self):
        """The book the church's latest hymn came from, as most churches
        sing from one, or else the first in use."""
        hymnals = self.hymnals_on_offer
        if not hymnals:
            return None
        last = (
            RolePiece.objects.for_organisation(self.organisation_id)
            .filter(hymn_entry__hymnal__in=hymnals)
            .order_by("-pk")
            .values_list("hymn_entry__hymnal_id", flat=True)
            .first()
        )
        return next((hymnal for hymnal in hymnals if hymnal.pk == last), hymnals[0])

    @cached_property
    def hymn_suggestions(self):
        """A Hymn slot's suggested hymns, with the church's own window for
        hymns (planning/suggestions.py)."""
        if not self.hymnals_on_offer:
            return []
        from core.models import SiteConfig

        from .suggestions import hymn_suggestions

        window = SiteConfig.of(self.service.organisation).hymn_repeat_window_weeks
        return hymn_suggestions(self, window)

    @property
    def proper_suggestions(self):
        """
        The day's chants this slot can take, in the order sung: a Proper
        slot its part's ("Ad te levavi" for the Introit; an Alleluia or
        Tract slot whichever the date has, or both), and an Antiphon, Responsory,
        Hymn or Canticle slot the day's chants of its kind, such as Palm
        Sunday's three antiphons. A chant already proposed in a slot of the
        same kind and part is left out, so a second Antiphon slot offers the
        antiphons the first hasn't taken.
        """
        chants = self.service.proper_chants
        if not chants:
            return []
        if self.kind == "proper" and self.proper_part == "alleluia_or_tract":
            # Only the Easter Vigil has both: in the Ordinary Form its Tracts
            # come after the readings, before the Alleluia; in 1962 the
            # Alleluia comes first, then the Tract.
            tracts, alleluias = chants.get("tract", []), chants.get("alleluia", [])
            # The service's form, not its occasion's: a weekday singing the
            # Sunday before's chants has no occasion.
            historic = self.service.effective_calendar_use() == "historic"
            offered = alleluias + tracts if historic else tracts + alleluias
        elif self.kind == "proper":
            offered = chants.get(self.proper_part, [])
        elif self.kind in MANY_CHANT_KINDS and not self.proper_part:
            offered = chants.get(self.kind, [])
        else:
            return []
        taken = self.service.references_proposed.get((self.kind, self.proper_part), set())
        return [incipit for incipit in offered if incipit not in taken]

    @property
    def takes_reference_first(self):
        """Hymns, psalms and antiphons are usually typed as a reference, so
        their add-piece form puts the reference box before the scores."""
        return self.kind in REFERENCE_FIRST

    @property
    def is_resolved(self):
        """Settled: marked not needed, or holding a confirmed piece. Uses
        .all(), so prefetched pieces cost no query."""
        return self.is_not_applicable or any(
            piece.is_confirmed for piece in self.pieces.all()
        )


class SlotTemplate(models.Model):
    """
    A named set of slots to add to a service in one go: Mass and Vespers
    come ready-made (each new church gets its own copies from
    accounts.organisations), and a conductor can edit those or make more.
    Its slots are TemplateSlot rows, each with a kind and proper part, so
    a service's slots arrive already classified. slot_names, the text the
    slots were first written as, is no longer read; it's dropped later.
    """

    # Whose template this is.
    organisation = models.ForeignKey(
        "accounts.Organisation", on_delete=models.CASCADE, related_name="slot_templates"
    )
    objects = OrganisationQuerySet.as_manager()
    name = models.CharField(max_length=50, help_text="e.g. Mass, Vespers, Benediction")
    slot_names = models.TextField(
        "slots", help_text="One slot per line, in the order of the service."
    )

    class Meta:
        ordering = ["name"]  # noqa
        constraints = [
            # Each church can have its own Mass, but only one.
            models.UniqueConstraint(fields=["organisation", "name"], name="slot_template_name_unique_per_organisation"),
        ]

    def __str__(self):
        return self.name

    @staticmethod
    def names_from_text(text):
        """Slot names from lines of text: trimmed, blank lines dropped, and
        each name once whatever its case."""
        names = []
        for line in text.splitlines():
            name = " ".join(line.split())
            if name and name.lower() not in (n.lower() for n in names):
                names.append(name)
        return names

    @property
    def slots(self):
        """The slot names in order. Uses .all(), so prefetched rows cost
        nothing."""
        return [slot.name for slot in self.template_slots.all()]

    def set_slots(self, names):
        """Make the template's slots these names, in order, each classified
        from its name as a new slot would be."""
        self.template_slots.all().delete()
        TemplateSlot.objects.bulk_create(
            TemplateSlot(
                template=self, organisation_id=self.organisation_id, name=name,
                kind=classify(name)[0], proper_part=classify(name)[1], position=position,
            )
            for position, name in enumerate(names, start=1)
        )

    def apply_to(self, service):
        """
        Add this template's slots to a service, in order, leaving out any
        it already has (whatever their case), so applying it twice adds
        nothing. Returns (added, already_there) as lists of names.
        """
        existing = {name.lower() for name in service.roles.values_list("role_name", flat=True)}
        added, already_there = [], []
        for slot in self.template_slots.all():
            if slot.name.lower() in existing:
                already_there.append(slot.name)
            else:
                ServiceRole.objects.create(
                    service=service, role_name=slot.name, kind=slot.kind, proper_part=slot.proper_part
                )
                added.append(slot.name)
        return added, already_there


class TemplateSlot(models.Model):
    """One slot of a template, as it'll be added to a service: its name,
    kind and proper part, in order."""

    template = models.ForeignKey(SlotTemplate, on_delete=models.CASCADE, related_name="template_slots")
    # Always its template's organisation, copied in save().
    organisation = models.ForeignKey(
        "accounts.Organisation", on_delete=models.CASCADE, related_name="template_slots"
    )
    objects = OrganisationQuerySet.as_manager()
    name = models.CharField("slot", max_length=50)
    kind = models.CharField(
        max_length=10, choices=KIND_CHOICES, blank=True, help_text="Leave it to be worked out from the slot's name."
    )
    proper_part = models.CharField(max_length=20, choices=PROPER_PART_CHOICES, blank=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]  # noqa

    def save(self, *args, **kwargs):
        self.organisation_id = self.template.organisation_id
        if not self.kind:
            self.kind, self.proper_part = classify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


# Said by the database's rule and by the propose form, which has to check
# it itself (RolePieceForm.clean): one wording for both.
ONE_PIECE_MESSAGE = "Choose one: a score, a hymn number or a reference."


class RolePiece(models.Model):
    # A piece's place in a score's history. The raw value names the CSS
    # class (badge--sung); the label is what people see.
    HISTORY_LABELS = {  # noqa
        "sung": "Sung",
        "scheduled": "Scheduled",
        "proposed": "Proposed",
    }

    service_role = models.ForeignKey(
        ServiceRole, on_delete=models.CASCADE, related_name="pieces"
    )
    # Always its slot's organisation, copied in save().
    organisation = models.ForeignKey(
        "accounts.Organisation", on_delete=models.CASCADE, related_name="role_pieces"
    )
    objects = OrganisationQuerySet.as_manager()
    # A piece is one of three: a score from the library, a hymn by its
    # number in one of the church's hymnals, or, for anything else such as
    # a psalm or chant, a short reference typed in. Never more than one.
    score = models.ForeignKey(
        "library.Score", null=True, blank=True, on_delete=models.PROTECT, related_name="role_pieces"
    )
    hymn_entry = models.ForeignKey(
        "library.HymnEntry", null=True, blank=True, on_delete=models.PROTECT, related_name="role_pieces"
    )
    # The tune a hymn is sung to here, when it isn't the book's own.
    tune = models.ForeignKey(
        "library.Tune", null=True, blank=True, on_delete=models.SET_NULL, related_name="role_pieces"
    )
    reference = models.CharField(max_length=200, blank=True, help_text='e.g. "NEH 123" or "Psalm 150, tone 4"')
    is_confirmed = models.BooleanField(default=False)
    comments = GenericRelation("comments.Comment")

    class Meta:
        ordering = ["id"]  # noqa
        constraints = [  # noqa
            models.CheckConstraint(
                condition=(
                    models.Q(score__isnull=False, hymn_entry__isnull=True, reference="")
                    | models.Q(score__isnull=True, hymn_entry__isnull=False, reference="")
                    | (models.Q(score__isnull=True, hymn_entry__isnull=True) & ~models.Q(reference=""))
                ),
                name="role_piece_one_of_three",
                violation_error_message=ONE_PIECE_MESSAGE,
            ),
            # A tune only means something for a hymn.
            models.CheckConstraint(
                condition=models.Q(tune__isnull=True) | models.Q(hymn_entry__isnull=False),
                name="role_piece_tune_only_for_a_hymn",
            ),
        ]

    def save(self, *args, **kwargs):
        self.organisation_id = self.service_role.organisation_id
        self.reference = self.reference.strip()
        super().save(*args, **kwargs)

    @property
    def title(self):
        """What the piece is called wherever it's shown: the score, the
        hymn's book and number ("NEH 53"), or the reference as typed."""
        if self.score_id:
            return str(self.score)
        if self.hymn_entry_id:
            return str(self.hymn_entry)
        return self.reference

    def __str__(self):
        return f"{self.title} ({'confirmed' if self.is_confirmed else 'proposed'})"

    @property
    def sheet_title(self):
        """
        How a piece prints for the congregation. A hymn sung to its book's
        own tune is just its number: "NEH 53". Sung to another tune, the
        tune is named by where it's printed in the same book, so a finger
        can be kept in the music, "NEH 53, tune NEH 115", or by its name
        if that book doesn't print it: "NEH 53, tune Repton".
        """
        if not self.hymn_entry_id or not self.tune_id or self.tune_id == self.hymn_entry.tune_id:
            return self.title
        hymnal = self.hymn_entry.hymnal
        number = self.tune.number_in(hymnal)
        return f"{self.title}, tune {hymnal.short_name} {number}" if number else f"{self.title}, tune {self.tune}"

    @property
    def sung_tune(self):
        """The tune a hymn is sung to: the one chosen here, or else the
        one its book prints it with. None for anything else."""
        if not self.hymn_entry_id:
            return None
        return self.tune or self.hymn_entry.tune

    def tune_choices(self):
        """
        The tunes a hymn piece could be sung to, in groups: the book's own
        tune for it; others in the same metre the same book prints, so a
        number can be given; then every other tune the church knows, as an
        organist may choose one from elsewhere. The metre is the hymn's,
        or failing that its usual tune's. Empty for anything not a hymn.
        """
        if not self.hymn_entry_id:
            return []
        entry = self.hymn_entry
        usual = entry.tune
        metre = entry.hymn.metre or (usual.metre if usual else "")
        tunes = list(Tune.objects.for_organisation(self.organisation_id).exclude(pk=getattr(usual, "pk", None)))
        in_book = set(
            HymnEntry.objects.filter(hymnal_id=entry.hymnal_id, tune__isnull=False).values_list("tune_id", flat=True)
        )
        same_metre = [tune for tune in tunes if metre and tune.metre == metre and tune.pk in in_book]
        others = [tune for tune in tunes if tune not in same_metre]
        groups = [
            ("Its usual tune", [usual] if usual else []),
            (f"Same metre, in {entry.hymnal.short_name}", same_metre),
            ("Other tunes", others),
        ]
        return [(label, group) for label, group in groups if group]

    def get_absolute_url(self):
        """A piece is shown on its service's page; the fragment jumps to
        its row (each has id="piece-row-<pk>")."""
        return f"{self.service_role.service.get_absolute_url()}#piece-row-{self.pk}"

    @property
    def history_state(self):
        """
        Derived, never stored: "sung" once confirmed for a service dated on
        or before today, "scheduled" if confirmed for a later one, otherwise
        "proposed". The same "today" rule as Score's last sung, so the
        history and the last-sung date always agree.
        """
        if not self.is_confirmed:
            return "proposed"
        if self.service_role.service.date <= timezone.localdate():
            return "sung"
        return "scheduled"

    @property
    def history_label(self):
        return self.HISTORY_LABELS[self.history_state]
