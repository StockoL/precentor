from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from .models import Score


class ScoreListView(ListView):
    model = Score
    context_object_name = "scores"


class ScoreDetailView(DetailView):
    model = Score


class ScoreCreateView(CreateView):
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
        "duration_minutes",
    ]


class ScoreUpdateView(UpdateView):
    model = Score
    fields = ScoreCreateView.fields


class ScoreDeleteView(DeleteView):
    model = Score
    success_url = reverse_lazy("library:score_list")
