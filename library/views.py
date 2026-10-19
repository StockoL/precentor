from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, F, ProtectedError
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from ordo.models import LiturgicalOccasion, LiturgicalSeason, UseType

from .forms import ScoreForm
from .models import Score, ScoreQuerySet


class ScoreListView(LoginRequiredMixin, ListView):
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
        if language:
            queryset = queryset.filter(language__iexact=language)
        if voicing:
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
            UseType.objects.filter(pk=use_type_pk).first()
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
        context["languages"] = (
            Score.objects.values_list("language", flat=True)
            .distinct()
            .order_by("language")
        )
        # Voicings actually in the library, with how many scores each.
        # The explicit order_by replaces the model's default ordering,
        # which would otherwise be added to the GROUP BY and split counts.
        context["voicings"] = (
            Score.objects.exclude(voicing="")
            .values("voicing")
            .annotate(count=Count("pk"))
            .order_by("voicing")
        )
        context["mixed_value"] = ScoreQuerySet.MIXED
        context["mixed_count"] = Score.objects.with_voicing(ScoreQuerySet.MIXED).count()
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
            }
            for key, label, _ in self.COLUMNS
        ]
        context["sort_label"] = next(label for key, label, _ in self.COLUMNS if key == sort)
        context["sort_direction"] = "ascending" if direction == "asc" else "descending"
        return context


class ScoreDetailView(LoginRequiredMixin, DetailView):
    model = Score


class ScoreCreateView(LoginRequiredMixin, CreateView):
    model = Score
    form_class = ScoreForm


class ScoreUpdateView(LoginRequiredMixin, UpdateView):
    model = Score
    form_class = ScoreForm


class ScoreDeleteView(LoginRequiredMixin, DeleteView):
    model = Score
    success_url = reverse_lazy("library:score_list")

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
