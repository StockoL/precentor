from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.urls import reverse


class Term(models.Model):
    name = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
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
    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name="services")
    date = models.DateField()
    service_type = models.CharField(max_length=50)
    occasion = models.ForeignKey(
        "ordo.LiturgicalOccasion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="services",
    )
    comments = GenericRelation("comments.Comment")

    class Meta:
        ordering = ["date"]  # noqa

    def __str__(self):
        return f"{self.service_type} — {self.date.strftime('%d/%m/%Y')}"

    def get_absolute_url(self):
        return reverse("planning:service_detail", kwargs={"pk": self.pk})

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
        for role in roles:
            if role.is_not_applicable or role.pieces.filter(is_confirmed=True).exists():
                resolved_count += 1

        if resolved_count == 0:
            return "not_started"
        if resolved_count == roles.count():
            return "complete"
        return "in_progress"

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


class ServiceRole(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="roles")
    role_name = models.CharField(max_length=50)
    is_not_applicable = models.BooleanField(default=False)

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
