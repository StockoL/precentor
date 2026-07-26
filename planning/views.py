from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from .models import Service, Term


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


class ServiceCreateView(CreateView):
    model = Service
    fields = ["date", "service_type", "occasion"]  # noqa

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["term"] = get_object_or_404(Term, pk=self.kwargs["term_pk"])
        return context

    def form_valid(self, form):
        form.instance.term = get_object_or_404(Term, pk=self.kwargs["term_pk"])
        return super().form_valid(form)


class ServiceDetailView(DetailView):
    model = Service

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["roles"] = self.object.roles.prefetch_related("pieces__score")
        return context


class ServiceUpdateView(UpdateView):
    model = Service
    fields = ServiceCreateView.fields


class ServiceDeleteView(DeleteView):
    model = Service

    def get_success_url(self):
        return self.object.term.get_absolute_url()
