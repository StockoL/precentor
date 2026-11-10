import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Count, F, ProtectedError, Q
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

from .forms import HymnalForm, HymnEntryForm, HymnForm, ScoreForm, ScoreImportForm, TuneForm
from .importing import (
    COLUMNS, IMPORT_EXAMPLE, MAX_BYTES, MAX_ROWS, ImportProblem, check_file, export_rows, save_import,
)
from .hymn_importing import HYMN_COLUMNS, HYMN_EXAMPLE, check_hymn_file, save_hymn_import
from .models import Hymn, Hymnal, HymnEntry, HymnImport, Score, ScoreImport, ScoreQuerySet, Tune
from .sheets import fetch_sheet


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

    # The Suitable-for filters: each address parameter and the tag it reads.
    SUITED_FOR = (
        ("suited_season", "suited_seasons"),
        ("suited_use_type", "suited_use_types"),
        ("suited_occasion", "suited_occasions"),
    )

    def suited_for_menus(self):
        """A menu for each Suitable-for filter, listing only what this
        church's scores are tagged with, and how many scores each, as the
        Voicing menu does. A menu with nothing in it is left out."""
        church = self.request.organisation
        kinds = (
            ("suited_season", "Season", LiturgicalSeason, ("name",)),
            ("suited_use_type", "Use", UseType, ("name",)),
            ("suited_occasion", "Occasion", LiturgicalOccasion, ("calendar_use", "name")),
        )
        menus = []
        for param, label, model, order in kinds:
            # Filtering before counting counts only this church's scores.
            tagged = (
                model.objects.filter(suited_scores__organisation=church)
                .annotate(count=Count("suited_scores", distinct=True))
                .order_by(*order)
            )
            options = [
                (str(tag.pk), getattr(tag, "choice_label", tag.name), tag.count) for tag in tagged
            ]
            if options:
                menus.append({"param": param, "label": label, "options": options,
                              "selected": self.request.GET.get(param, "")})
        return menus

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

        # What a score suits: only those tagged for each one chosen. Each
        # is one tag, so a score never comes back twice from the joins.
        for param, field in self.SUITED_FOR:
            chosen = self.request.GET.get(param, "")
            if chosen.isdigit():
                queryset = queryset.filter(**{field: chosen})
        queryset = queryset.with_last_sung()

        sort, direction = self.sort()
        fields = next(fields for key, _, fields in self.COLUMNS if key == sort)
        # Blanks (no duration, never sung) go last whichever way it runs.
        first = F(fields[0])
        first = first.desc(nulls_last=True) if direction == "desc" else first.asc(nulls_last=True)
        ordering = [first, *fields[1:]]
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
        context["suited_for"] = self.suited_for_menus()
        context["filters_active"] = any(
            (context["query"], context["selected_language"], context["selected_voicing"])
        ) or any(menu["selected"] for menu in context["suited_for"])

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
    """What the score form page needs beyond the form itself. Opened from
    elsewhere with ?next=, such as a service asking for a voicing, it goes
    back there after saving."""

    def next_url(self):
        return safe_next(self.request, self.request.POST.get("next") or self.request.GET.get("next"))

    def get_success_url(self):
        return self.next_url() or super().get_success_url()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(next=self.next_url(), **kwargs)
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
    """A new score. A service's "Add to library" link fills in the title
    with ?title=, from the reference typed there."""

    model = Score
    form_class = ScoreForm

    def get_initial(self):
        return {**super().get_initial(), "title": self.request.GET.get("title", "")}


class ScoreUpdateView(LibraryEditRequiredMixin, OrganisationScopedMixin, ScoreFormMixin, UpdateView):
    model = Score
    form_class = ScoreForm


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
                f'"{self.object}" can\'t be deleted: it has been proposed or '
                "confirmed in at least one service, and that history is "
                "preserved deliberately.",
            )
            return redirect(self.object.get_absolute_url())
        return redirect(self.get_success_url())


@login_required
def completeness(request):
    """What the library's details are missing, as counts that link to the
    Library's own filters, and the motet and antiphon scores with no text
    listed by name, as no filter shows those. Hymns are listed by where
    they're printed, as one with no first line has no other name."""
    scores = own(Score, request)
    hymns = list(own(Hymn, request).prefetch_related("entries__hymnal", "suited_seasons"))
    for hymn in hymns:
        hymn.printed_at = ", ".join(str(entry) for entry in hymn.entries.all())
    return render(request, "library/completeness.html", {
        "no_voicing": scores.filter(voicing="").count(),
        "no_language": scores.filter(language="").count(),
        "needing_text": list(scores.needing_text().order_by("title")),
        "unspecified": ScoreQuerySet.UNSPECIFIED,
        "has_hymns": bool(hymns),
        "hymn_lines": [
            ("with no first line", "Every hymn has its first line.", [h for h in hymns if not h.first_line]),
            ("with no words", "Every hymn has its words.", [h for h in hymns if not h.text]),
            ("not tagged for any season", "Every hymn is tagged for a season.",
             [h for h in hymns if not h.suited_seasons.all()]),
        ],
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


def read_import(form):
    """
    What an import form brought: (the field it came by, its bytes, a name
    for it), from the chosen file or the pasted Google Sheets link. Raises
    ImportProblem if the sheet can't be fetched, to show beside that field.
    """
    upload = form.cleaned_data["file"]
    if upload:
        # One byte past the limit is enough to know it's too big.
        return "file", upload.read(MAX_BYTES + 1), upload.name
    return "sheet_link", fetch_sheet(form.cleaned_data["sheet_link"]), "a Google Sheet"


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
        # The reasons go beside whichever was used, the file or the link.
        source = "file" if form.cleaned_data["file"] else "sheet_link"
        try:
            _, data, name = read_import(form)
            checked = check_file(data, self.request.organisation)
        except ImportProblem as problem:
            form.add_error(source, str(problem))
            return self.form_invalid(form)
        if not checked.scores:
            reasons = "; ".join(f"row {number}: {why}" for number, why in checked.skipped[:5])
            form.add_error(source, f"None of the rows could be imported ({reasons}).")
            return self.form_invalid(form)
        batch = save_import(checked, self.request.organisation, self.request.user, name)
        return redirect("library:score_import_detail", pk=batch.pk)


class ScoreImportDetailView(LibraryEditRequiredMixin, OrganisationScopedMixin, DetailView):
    """What an import brought in: how many scores, the rows skipped and
    why, likely duplicates, and how many still need a voicing."""

    model = ScoreImport
    context_object_name = "score_import"
    template_name = "library/score_import_detail.html"
    # The most scores listed on the page; a longer import says how many.
    LISTED = 100

    def get_context_data(self, **kwargs):
        scores = self.object.scores.all()
        return super().get_context_data(
            can_remove=can_remove_import(self.request.user, self.object),
            no_voicing=scores.filter(voicing="").count(),
            unspecified=ScoreQuerySet.UNSPECIFIED,
            # In the library's own order (Score.Meta), in one query: each
            # row reads only the score's own fields.
            imported_scores=scores[: self.LISTED],
            imported_count=scores.count(),
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


class HymnalListView(LoginRequiredMixin, OrganisationScopedMixin, ListView):
    """The church's hymnals, those in use first; archived ones are listed
    on their own beneath."""

    model = Hymnal
    context_object_name = "hymnals"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["in_use"] = [hymnal for hymnal in context["hymnals"] if not hymnal.archived]
        context["archived"] = [hymnal for hymnal in context["hymnals"] if hymnal.archived]
        return context


class HymnalDetailView(LoginRequiredMixin, OrganisationScopedMixin, DetailView):
    """A hymnal and the hymns the church has recorded from it, by number."""

    model = Hymnal
    context_object_name = "hymnal"

    def get_context_data(self, **kwargs):
        waiting = self.object.imports.filter(status=HymnImport.PENDING).first()
        return super().get_context_data(entries=self.object.numbered_entries(), waiting=waiting, **kwargs)


class HymnDetailView(LoginRequiredMixin, OrganisationScopedMixin, DetailView):
    """A hymn: where it's printed, when it was last sung, its words and
    what it suits."""

    model = Hymn
    context_object_name = "hymn"

    def get_queryset(self):
        return super().get_queryset().with_last_sung().prefetch_related(
            "suited_use_types", "suited_seasons", "suited_occasions"
        )

    def get_context_data(self, **kwargs):
        entries = sorted(self.object.entries.select_related("hymnal", "tune"), key=HymnEntry.number_order)
        # Hymns that may be this one printed elsewhere, each with where.
        matches = [
            (other, ", ".join(str(entry) for entry in other.entries.all()))
            for other in self.object.possible_matches()
        ] if can_edit_library(self.request.user) else []
        return super().get_context_data(entries=entries, matches=matches, **kwargs)


@role_required(can_edit_library)
@require_POST
def same_hymn(request, pk, other_pk):
    """Answer "is this the same hymn?": yes joins the two, keeping every
    entry and the services that used them; no is remembered, so it isn't
    asked again. Both hymns must be the church's own."""
    hymn = get_object_or_404(own(Hymn, request), pk=pk)
    other = get_object_or_404(own(Hymn, request).exclude(pk=pk), pk=other_pk)
    if request.POST.get("answer") == "same":
        hymn.absorb(other)
        messages.success(request, "Joined: they're one hymn now, under every number it's printed at.")
    else:
        hymn.not_same_as.add(other)
        messages.success(request, "Noted: they're different hymns, and you won't be asked again.")
    return redirect(hymn)


class HymnUpdateView(LibraryEditRequiredMixin, OrganisationScopedMixin, UpdateView):
    """A hymn's details. Opened from a service with ?next=, it goes back
    there after saving; otherwise to the hymn's page."""

    model = Hymn
    form_class = HymnForm

    def next_url(self):
        return safe_next(self.request, self.request.POST.get("next") or self.request.GET.get("next"))

    def get_success_url(self):
        return self.next_url() or self.object.get_absolute_url()

    def get_context_data(self, **kwargs):
        return super().get_context_data(next=self.next_url(), **kwargs)


class HymnEntryUpdateView(LibraryEditRequiredMixin, OrganisationScopedMixin, UpdateView):
    """The tune a book prints a hymn with; back to the hymn's page."""

    model = HymnEntry
    form_class = HymnEntryForm
    context_object_name = "entry"

    def get_success_url(self):
        return self.object.hymn.get_absolute_url()


class TuneListView(LoginRequiredMixin, OrganisationScopedMixin, ListView):
    model = Tune
    context_object_name = "tunes"


class TuneCreateView(LibraryEditRequiredMixin, OrganisationCreateMixin, CreateView):
    model = Tune
    form_class = TuneForm
    success_url = reverse_lazy("library:tune_list")


class TuneUpdateView(LibraryEditRequiredMixin, OrganisationScopedMixin, UpdateView):
    model = Tune
    form_class = TuneForm
    success_url = reverse_lazy("library:tune_list")


class HymnalCreateView(LibraryEditRequiredMixin, OrganisationCreateMixin, CreateView):
    model = Hymnal
    form_class = HymnalForm
    success_url = reverse_lazy("library:hymnal_list")


class HymnalUpdateView(LibraryEditRequiredMixin, OrganisationScopedMixin, UpdateView):
    model = Hymnal
    form_class = HymnalForm
    success_url = reverse_lazy("library:hymnal_list")


class HymnalDeleteView(LibraryEditRequiredMixin, OrganisationScopedMixin, DeletePageMixin, DeleteView):
    model = Hymnal
    success_url = reverse_lazy("library:hymnal_list")
    gone_url = success_url
    gone_message = "That hymnal has already been deleted."

    def post(self, request, *args, **kwargs):
        """A hymnal hymns have been recorded from is kept, as their history
        would go with it; the message says to archive it instead."""
        self.object = self.get_object()
        try:
            self.object.delete()
        except ProtectedError:
            messages.error(
                request,
                f"{self.object} has hymns recorded from it, so it's kept. Archive it instead "
                "to keep it out of the way.",
            )
            return redirect("library:hymnal_update", pk=self.object.pk)
        return redirect(self.get_success_url())


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


@role_required(can_edit_library)
def hymn_import_template(request):
    """The headers of a hymnal list, as a CSV to fill in, made from
    HYMN_COLUMNS like the score template is from COLUMNS."""
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="precentor-hymnal-template.csv"'
    response.write("﻿")
    csv.writer(response).writerow([header for header, _, _ in HYMN_COLUMNS])
    return response


class HymnImportView(LibraryEditRequiredMixin, FormView):
    """Import a list into one hymnal, from a file or a Google Sheets link.
    The book is chosen by the address, so every row belongs to it."""

    form_class = ScoreImportForm
    template_name = "library/hymn_import.html"

    def dispatch(self, request, *args, **kwargs):
        self.hymnal = get_object_or_404(own(Hymnal, request), pk=kwargs["pk"], archived=False)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            hymnal=self.hymnal, columns=HYMN_COLUMNS, example=HYMN_EXAMPLE, max_bytes=MAX_BYTES, **kwargs
        )

    def form_valid(self, form):
        source = "file" if form.cleaned_data["file"] else "sheet_link"
        try:
            _, data, name = read_import(form)
            checked = check_hymn_file(data)
        except ImportProblem as problem:
            form.add_error(source, str(problem))
            return self.form_invalid(form)
        if not checked.rows:
            reasons = "; ".join(f"row {number}: {why}" for number, why in checked.skipped[:5])
            form.add_error(source, f"None of the rows could be imported ({reasons}).")
            return self.form_invalid(form)
        batch = save_hymn_import(checked, self.hymnal, self.request.user, name)
        if batch is None:
            messages.info(self.request, f"{self.hymnal.short_name} already had everything in that list.")
            return redirect(self.hymnal)
        return redirect("library:hymn_import_detail", pk=batch.pk)


class HymnImportDetailView(LibraryEditRequiredMixin, OrganisationScopedMixin, DetailView):
    """What a hymnal import added and filled in, and the rows skipped."""

    model = HymnImport
    context_object_name = "hymn_import"
    template_name = "library/hymn_import_detail.html"
    # The most rows listed on the page; a longer import says how many.
    LISTED = 100
    FILLED_LABELS = {"first_line": "first line", "metre": "metre", "tune_id": "tune"}

    def changed_entries(self):
        """The entries this import added or filled in, in the book's
        number order, each with what happened to it. Two queries: what
        it filled is recorded in its changes, as removing it needs."""
        batch = self.object
        filled = {}  # entry pk or ("hymn", pk): the labels of what was filled
        for model, pk, attribute, _ in batch.changes.get("filled", []):
            key = pk if model == "HymnEntry" else ("hymn", pk)
            filled.setdefault(key, []).append(self.FILLED_LABELS.get(attribute, attribute))
        hymn_pks = [key[1] for key in filled if isinstance(key, tuple)]
        entry_pks = [key for key in filled if not isinstance(key, tuple)]
        entries = batch.hymnal.entries.filter(
            Q(import_batch=batch) | Q(hymn_id__in=hymn_pks) | Q(pk__in=entry_pks)
        ).select_related("hymn", "tune")
        rows = []
        for entry in sorted(entries, key=HymnEntry.number_order):
            if entry.import_batch_id == batch.pk:
                entry.change = "Added"
            else:
                labels = filled.get(("hymn", entry.hymn_id), []) + filled.get(entry.pk, [])
                entry.change = "Filled in: " + ", ".join(labels)
            rows.append(entry)
        return rows

    def get_context_data(self, **kwargs):
        rows = self.changed_entries()
        return super().get_context_data(
            can_remove=can_remove_import(self.request.user, self.object),
            changed_entries=rows[: self.LISTED],
            changed_count=len(rows),
            new_tunes=Tune.objects.filter(pk__in=self.object.changes.get("tunes", [])).order_by("name"),
            **kwargs,
        )


@role_required(can_edit_library)
@require_POST
def keep_hymn_import(request, pk):
    """Keep a pending hymnal import for good, as for scores."""
    hymn_import = get_object_or_404(own(HymnImport, request), pk=pk, status=HymnImport.PENDING)
    hymn_import.keep()
    messages.success(request, f"Kept the import into {hymn_import.hymnal.short_name}.")
    return redirect(hymn_import.hymnal)


@login_required
def remove_hymn_import(request, pk):
    """Undo a pending hymnal import, after asking; Back or a second click
    goes to the hymnals with a message, as for scores."""
    hymn_import = own(HymnImport, request).filter(pk=pk, status=HymnImport.PENDING).first()
    if hymn_import is None:
        messages.info(request, "That import has already been removed or kept.")
        return redirect("library:hymnal_list")
    if not can_remove_import(request.user, hymn_import):
        raise PermissionDenied
    hymnal = hymn_import.hymnal
    if request.method == "POST":
        removed, kept = hymn_import.remove()
        message = f"Removed the import into {hymnal.short_name}: {removed} hymn{pluralize(removed)} taken out."
        if kept:
            message += f" {kept} {pluralize(kept, 'has,have')} been sung, so kept."
        messages.success(request, message)
        return redirect(hymnal)
    in_use = hymn_import.entries.filter(role_pieces__isnull=False).distinct().count()
    return render(request, "library/hymn_import_confirm_remove.html", {
        "hymn_import": hymn_import, "removing": hymn_import.entries.count() - in_use, "in_use": in_use,
    })
