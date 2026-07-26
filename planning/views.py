from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from .models import Term


class TermListView(ListView):
    model = Term
    context_object_name = "terms"


class TermDetailView(DetailView):
    model = Term

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["services"] = self.object.services.all()
        return context


class TermCreateView(CreateView):
    model = Term
    fields = ["name", "start_date", "end_date"]  # noqa


class TermUpdateView(UpdateView):
    model = Term
    fields = TermCreateView.fields


class TermDeleteView(DeleteView):
    model = Term
    success_url = reverse_lazy("planning:term_list")
