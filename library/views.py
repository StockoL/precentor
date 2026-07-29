from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import ProtectedError
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

from .models import Score


class ScoreListView(LoginRequiredMixin, ListView):
    model = Score
    context_object_name = "scores"

    def get_queryset(self):
        queryset = super().get_queryset()
        language = self.request.GET.get("language")
        voice_part = self.request.GET.get("voice_part")

        if language:
            queryset = queryset.filter(language__iexact=language)

        voice_part_lookup = {
            "soprano": "soprano_parts__gt",
            "alto": "alto_parts__gt",
            "tenor": "tenor_parts__gt",
            "bass": "bass_parts__gt",
        }
        if voice_part in voice_part_lookup:
            queryset = queryset.filter(**{voice_part_lookup[voice_part]: 0})

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

        return queryset.ranked_by_suitability(
            occasion=occasion, season=season, use_type=use_type
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["languages"] = (
            Score.objects.values_list("language", flat=True)
            .distinct()
            .order_by("language")
        )
        context["selected_language"] = self.request.GET.get("language", "")
        context["selected_voice_part"] = self.request.GET.get("voice_part", "")
        return context


class ScoreDetailView(LoginRequiredMixin, DetailView):
    model = Score


class ScoreCreateView(LoginRequiredMixin, CreateView):
    model = Score
    fields = [  # noqa
        "title",
        "composer",
        "arranger",
        "voicing",
        "soprano_parts",
        "alto_parts",
        "tenor_parts",
        "bass_parts",
        "language",
        "lead_time_tag",
        "copies_owned",
        "filing_location",
        "suited_use_types",
        "suited_seasons",
        "suited_occasions",
        "duration_minutes",
    ]


class ScoreUpdateView(LoginRequiredMixin, UpdateView):
    model = Score
    fields = ScoreCreateView.fields


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
