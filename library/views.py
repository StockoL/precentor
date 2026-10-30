import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Count, F, ProtectedError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.defaultfilters import pluralize
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    FormView,
    ListView,
    UpdateView,
)

from accounts.decorators import role_required
from accounts.mixins import OrganisationCreateMixin, OrganisationScopedMixin, RoleRequiredMixin
from accounts.permissions import can_edit_library, can_remove_import
from accounts.querysets import own
from ordo.models import LiturgicalOccasion, LiturgicalSeason, UseType
from precentor_project.mixins import DeletePageMixin
from precentor_project.utils import safe_next

from .forms import ScoreForm, ScoreImportForm
from .importing import (
    COLUMNS, IMPORT_EXAMPLE, MAX_BYTES, MAX_ROWS, ImportProblem, check_file, export_rows, save_import,
)
from .models import Score, ScoreImport, ScoreQuerySet


class ScoreListView(LoginRequiredMixin, OrganisationScopedMixin, ListView):
    model = Score
    context_object_name = "scores"
    paginate_by = 50

    # Table columns: (sort key, heading, fields to order by). The first
    # field follows the chosen direction; the rest are tie-breaks in
    # catalogue order. Every column is sortable.
    COLUMNS = [
        ("composer", "Composer", ["composer_surname", "composer_other_names", "title"]),
        ("title", "Title", ["title", "composer_surname"]),
        ("voicing", "Voicing", ["voicing", "composer_surname", "title"]),
        ("language", "Language", ["language", "composer_surname", "title"]),
        ("duration", "Duration", ["duration_minutes", "composer_surname", "title"]),
        ("copies", "Copies", ["copies_owned", "composer_surname", "title"]),
        ("location", "Filing location", ["filing_location", "composer_surname", "title"]),
        ("last_sung", "Last sung", ["last_sung", "composer_surname", "title"]),
    ]
    DEFAULT_SORT = "composer"
    # Right-aligned, so their figures line up.
    NUMERIC_COLUMNS = ("duration", "copies")

    def sort(self):
        """The chosen column and direction, falling back to the default
        for anything unrecognised in the query string."""
        keys = [key for key, _, _ in self.COLUMNS]
        sort = self.request.GET.get("sort")
        direction = self.request.GET.get("dir")
        return (
            sort if sort in keys else self.DEFAULT_SORT,
            direction if direction in ("asc", "desc") else "asc",
        )

    def get_queryset(self):
        queryset = super().get_queryset()
        query = self.request.GET.get("q", "").strip()
        language = self.request.GET.get("language")
        voicing = self.request.GET.get("voicing")

        if query:
            queryset = queryset.search(query)
        if language == ScoreQuerySet.UNSPECIFIED:
            queryset = queryset.filter(language="")
        elif language:
            queryset = queryset.filter(language__iexact=language)
        if voicing == ScoreQuerySet.UNSPECIFIED:
            queryset = queryset.filter(voicing="")
        elif voicing:
            queryset = queryset.with_voicing(voicing)

        occasion_pk = self.request.GET.get("suited_occasion")
        season_pk = self.request.GET.get("suited_season")
        use_type_pk = self.request.GET.get("suited_use_type")

        occasion = (
            LiturgicalOccasion.objects.filter(pk=occasion_pk).first()
            if occasion_pk and occasion_pk.isdigit()
            else None
        )
        season = (
            LiturgicalSeason.objects.filter(pk=season_pk).first()
            if season_pk and season_pk.isdigit()
            else None
        )
        use_type = (
            UseType.objects.for_organisation(self.request.organisation).filter(pk=use_type_pk).first()
            if use_type_pk and use_type_pk.isdigit()
            else None
        )

        ranked = any((occasion, season, use_type))
        queryset = queryset.ranked_by_suitability(
            occasion=occasion, season=season, use_type=use_type
        ).with_last_sung()

        sort, direction = self.sort()
        fields = next(fields for key, _, fields in self.COLUMNS if key == sort)
        # Blanks (no duration, never sung) go last whichever way it runs.
        first = F(fields[0])
        first = first.desc(nulls_last=True) if direction == "desc" else first.asc(nulls_last=True)
        ordering = [first, *fields[1:]]
        if ranked:
            # Suited scores still come first; the sort orders within that.
            ordering.insert(0, "-is_suited")
        return queryset.order_by(*ordering)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # A blank language would add an option with the same empty value
        # as "Any", which the browser then shows as selected.
        scores = Score.objects.for_organisation(self.request.organisation)
        context["languages"] = (
            scores.exclude(language="")
            .values_list("language", flat=True)
            .distinct()
            .order_by("language")
        )
        # Voicings actually in the library, with how many scores each.
        # The explicit order_by replaces the model's default ordering,
        # which would otherwise be added to the GROUP BY and split counts.
        context["voicings"] = (
            scores.exclude(voicing="")
            .values("voicing")
            .annotate(count=Count("pk"))
            .order_by("voicing")
        )
        # How many have no language or voicing yet, so they can be found
        # and filled in; each menu offers this only when there are some.
        context["unspecified_value"] = ScoreQuerySet.UNSPECIFIED
        context["unspecified_language_count"] = scores.filter(language="").count()
        context["unspecified_voicing_count"] = scores.filter(voicing="").count()
        # Imports still waiting to be kept or removed, for the people who
        # can do either, so one isn't forgotten.
        if can_edit_library(self.request.user):
            context["pending_imports"] = (
                ScoreImport.objects.for_organisation(self.request.organisation)
                .filter(status=ScoreImport.PENDING)
                .annotate(score_count=Count("scores"))
            )
        context["mixed_value"] = ScoreQuerySet.MIXED
        context["mixed_count"] = scores.with_voicing(ScoreQuerySet.MIXED).count()
        context["query"] = self.request.GET.get("q", "").strip()
        context["selected_language"] = self.request.GET.get("language", "")
        context["selected_voicing"] = self.request.GET.get("voicing", "")
        context["filters_active"] = any(
            (context["query"], context["selected_language"], context["selected_voicing"])
        )

        # Each heading's sort state, worked out here because a template
        # can't do this logic cleanly: aria-sort for the sorted column,
        # and which direction each heading's link should ask for next.
        sort, direction = self.sort()
        context["columns"] = [
            {
                "key": key,
                "label": label,
                "aria_sort": ("ascending" if direction == "asc" else "descending")
                if key == sort
                else None,
                "next_dir": "desc" if key == sort and direction == "asc" else "asc",
                "numeric": key in self.NUMERIC_COLUMNS,
            }
            for key, label, _ in self.COLUMNS
        ]
        context["sort_label"] = next(label for key, label, _ in self.COLUMNS if key == sort)
        context["sort_direction"] = "ascending" if direction == "asc" else "descending"
        return context


class ScoreDetailView(LoginRequiredMixin, OrganisationScopedMixin, DetailView):
    model = Score

    def get_queryset(self):
        return super().get_queryset().with_last_sung()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Every service the piece has been proposed or confirmed for,
        # newest first. Through the reverse relation, so library doesn't
        # import planning; select_related loads each service in one query.
        context["history"] = self.object.role_pieces.select_related(
            "service_role__service__term"
        ).order_by("-service_role__service__date")
        return context


class LibraryEditRequiredMixin(RoleRequiredMixin):
    """For the pages that add, change or delete a score."""

    permission = can_edit_library


class ScoreFormMixin:
    """What the score form page needs beyond the form itself."""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # For the voicing field's <datalist> of suggestions.
        context["existing_voicings"] = (
            Score.objects.for_organisation(self.request.organisation)
            .exclude(voicing="")
            .order_by("voicing")
            .values_list("voicing", flat=True)
            .distinct()
        )
        return context


class ScoreCreateView(LibraryEditRequiredMixin, OrganisationCreateMixin, ScoreFormMixin, CreateView):
    model = Score
    form_class = ScoreForm


class ScoreUpdateView(LibraryEditRequiredMixin, OrganisationScopedMixin, ScoreFormMixin, UpdateView):
    """Editing a score. Opened from elsewhere with ?next=, such as a service
    asking for a voicing, it goes back there after saving."""

    model = Score
    form_class = ScoreForm

    def next_url(self):
        return safe_next(self.request, self.request.POST.get("next") or self.request.GET.get("next"))

    def get_success_url(self):
        return self.next_url() or super().get_success_url()

    def get_context_data(self, **kwargs):
        return super().get_context_data(next=self.next_url(), **kwargs)


class ScoreDeleteView(LibraryEditRequiredMixin, OrganisationScopedMixin, DeletePageMixin, DeleteView):
    model = Score
    success_url = reverse_lazy("library:score_list")
    gone_url = success_url
    gone_message = "That score has already been deleted."

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        try:
            self.object.delete()
        except ProtectedError:
            messages.error(
                request,
                f'"{self.object}" can\'t be deleted — it has been proposed or '
                "confirmed in at least one service, and that history is "
                "preserved deliberately.",
            )
            return redirect(self.object.get_absolute_url())
        return redirect(self.get_success_url())


@login_required
def completeness(request):
    """What the library's details are missing, as counts that link to the
    Library's own filters, and the motet and antiphon scores with no text
    listed by name, as no filter shows those."""
    scores = own(Score, request)
    return render(request, "library/completeness.html", {
        "no_voicing": scores.filter(voicing="").count(),
        "no_language": scores.filter(language="").count(),
        "needing_text": list(scores.needing_text().order_by("title")),
        "unspecified": ScoreQuerySet.UNSPECIFIED,
    })


@role_required(can_edit_library)
def import_template(request):
    """The headers of Precentor's import format, as a CSV to fill in. It's
    made from COLUMNS, so it always matches what the import expects. The
    byte-order mark at the start makes Excel open it as UTF-8."""
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="precentor-library-template.csv"'
    response.write("\ufeff")
    csv.writer(response).writerow([header for header, _, _ in COLUMNS])
    return response


@role_required(can_edit_library)
def export_library(request):
    """The church's whole library as a CSV in the import's own format, so
    it can be kept as a copy, edited in a spreadsheet or imported again.
    The date in the file name tells one copy from another."""
    scores = own(Score, request).order_by("composer_surname", "title")
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = (
        f'attachment; filename="precentor-library-{timezone.localdate().isoformat()}.csv"'
    )
    response.write("﻿")
    csv.writer(response).writerows(export_rows(scores))
    return response


class ScoreImportView(LibraryEditRequiredMixin, FormView):
    """Upload a spreadsheet. A file that can't work, or has no usable rows,
    comes back with the reasons; otherwise the scores are saved as one
    pending import and the result page shows what happened."""

    form_class = ScoreImportForm
    template_name = "library/score_import.html"

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            columns=COLUMNS, max_rows=MAX_ROWS, max_bytes=MAX_BYTES, example=IMPORT_EXAMPLE, **kwargs
        )

    def form_valid(self, form):
        upload = form.cleaned_data["file"]
        # One byte past the limit is enough to know it's too big.
        data = upload.read(MAX_BYTES + 1)
        try:
            checked = check_file(data, self.request.organisation)
        except ImportProblem as problem:
            form.add_error("file", str(problem))
            return self.form_invalid(form)
        if not checked.scores:
            reasons = "; ".join(f"row {number}: {why}" for number, why in checked.skipped[:5])
            form.add_error("file", f"None of the rows could be imported ({reasons}).")
            return self.form_invalid(form)
        batch = save_import(checked, self.request.organisation, self.request.user, upload.name)
        return redirect("library:score_import_detail", pk=batch.pk)


class ScoreImportDetailView(LibraryEditRequiredMixin, OrganisationScopedMixin, DetailView):
    """What an import brought in: how many scores, the rows skipped and
    why, likely duplicates, and how many still need a voicing."""

    model = ScoreImport
    context_object_name = "score_import"
    template_name = "library/score_import_detail.html"

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            can_remove=can_remove_import(self.request.user, self.object),
            no_voicing=self.object.scores.filter(voicing="").count(),
            unspecified=ScoreQuerySet.UNSPECIFIED,
            **kwargs,
        )


@role_required(can_edit_library)
@require_POST
def keep_import(request, pk):
    """Keep a pending import's scores for good. Only a pending import of
    the church's own can be found, so keeping twice is a 404, not an error."""
    score_import = get_object_or_404(own(ScoreImport, request), pk=pk, status=ScoreImport.PENDING)
    score_import.keep()
    count = score_import.scores.count()
    messages.success(request, f"Kept {count} score{pluralize(count)} from {score_import.original_filename}.")
    return redirect("library:score_list")


@login_required
def remove_import(request, pk):
    """
    Remove a pending import: its scores are deleted, except any already
    planned into a service, which are kept. Asks first. If the import has
    already been removed or kept (Back, or a second click), the person
    goes to the library with a message rather than a "not found" page.
    """
    score_import = own(ScoreImport, request).filter(pk=pk, status=ScoreImport.PENDING).first()
    if score_import is None:
        messages.info(request, "That import has already been removed or kept.")
        return redirect("library:score_list")
    if not can_remove_import(request.user, score_import):
        raise PermissionDenied
    if request.method == "POST":
        name = score_import.original_filename
        deleted, kept = score_import.remove()
        message = f"Removed {deleted} score{pluralize(deleted)} imported from {name}."
        if kept:
            message += f" {kept} {pluralize(kept, 'is,are')} planned into services, so kept."
        messages.success(request, message)
        return redirect("library:score_list")
    in_use = score_import.scores.filter(role_pieces__isnull=False).distinct().count()
    return render(request, "library/score_import_confirm_remove.html", {
        "score_import": score_import,
        "removing": score_import.scores.count() - in_use,
        "in_use": in_use,
    })


class ScoreImportListView(LibraryEditRequiredMixin, OrganisationScopedMixin, ListView):
    """The church's imports: those waiting to be kept or removed first,
    then the newest."""

    model = ScoreImport
    context_object_name = "imports"
    template_name = "library/score_import_list.html"

    def get_queryset(self):
        # "pending" sorts after "kept", so status descending puts the
        # waiting ones first.
        return (
            super().get_queryset()
            .select_related("created_by")
            .annotate(score_count=Count("scores"))
            .order_by("-status", "-created_at")
        )
