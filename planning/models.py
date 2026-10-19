from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.urls import reverse
from django.utils.formats import date_format

from ordo.models import CALENDAR_USE_CHOICES


class Term(models.Model):
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
    comments = GenericRelation("comments.Comment")

    class Meta:
        ordering = ["date"]  # noqa

    def __str__(self):
        return f"{self.service_type} — {date_format(self.date)}"

    def get_absolute_url(self):
        return reverse("planning:service_detail", kwargs={"pk": self.pk})

    def effective_calendar_use(self):
        return self.calendar_use or self.term.calendar_use

    @property
    def status(self):
        """
        Derived, never stored: not_started / in_progress / complete.
        A role counts as "resolved" if it's marked N/A, or if it has
        at least one confirmed piece.
        """
        roles = self.roles.all()
        if not roles:
            return "not_started"

        resolved_count = 0
        has_any_piece = False
        for role in roles:
            if role.is_not_applicable:
                resolved_count += 1
                continue
            if role.pieces.exists():
                has_any_piece = True
            if role.pieces.filter(is_confirmed=True).exists():
                resolved_count += 1

        if resolved_count == roles.count():
            return "complete"
        if resolved_count == 0 and not has_any_piece:
            return "not_started"
        return "in_progress"

    @property
    def status_label(self):
        """The status as shown in the UI, e.g. "Not started". Status is
        derived, not a choices field, so there's no get_status_display()."""
        return self.STATUS_LABELS[self.status]

    def music_list_rows(self, draft=False):
        rows = []
        for role in self.roles.all():
            if role.is_not_applicable:
                continue
            confirmed = [p.score for p in role.pieces.all() if p.is_confirmed]
            if not confirmed and not draft:
                continue
            rows.append({"role_name": role.role_name, "pieces": confirmed})
        return rows


class TermMarker(models.Model):
    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name="markers")
    date = models.DateField()
    # "Notice" is the UI word for a TermMarker.
    text = models.CharField("notice", max_length=200)

    class Meta:
        ordering = ["date"]  # noqa

    def __str__(self):
        return f"{self.text} ({date_format(self.date)})"


class ServiceRole(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="roles")
    # "Slot" is the UI word for a ServiceRole.
    role_name = models.CharField("slot", max_length=50)
    is_not_applicable = models.BooleanField("not needed (N/A)", default=False)

    class Meta:
        ordering = ["id"]  # noqa

    def __str__(self):
        return f"{self.role_name} ({self.service})"


class RolePiece(models.Model):
    service_role = models.ForeignKey(
        ServiceRole, on_delete=models.CASCADE, related_name="pieces"
    )
    score = models.ForeignKey(
        "library.Score", on_delete=models.PROTECT, related_name="role_pieces"
    )
    is_confirmed = models.BooleanField(default=False)
    comments = GenericRelation("comments.Comment")

    class Meta:
        ordering = ["id"]  # noqa

    def __str__(self):
        return f"{self.score} ({'confirmed' if self.is_confirmed else 'proposed'})"
