from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from .forms import RolePieceForm, ServiceRoleForm
from .mixins import ConductorRequiredMixin
from .models import RolePiece, Service, ServiceRole, Term


def is_conductor(user):
    return user.groups.filter(name="Conductor").exists()


# --- Term views ---


class TermListView(LoginRequiredMixin, ListView):
    model = Term
    context_object_name = "terms"


class TermDetailView(LoginRequiredMixin, DetailView):
    model = Term

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["services"] = self.object.services.all()
        return context


class TermCreateView(ConductorRequiredMixin, CreateView):
    model = Term
    fields = ["name", "start_date", "end_date"]


class TermUpdateView(ConductorRequiredMixin, UpdateView):
    model = Term
    fields = TermCreateView.fields


class TermDeleteView(ConductorRequiredMixin, DeleteView):
    model = Term
    success_url = reverse_lazy("planning:term_list")


# --- Service views ---


class ServiceCreateView(ConductorRequiredMixin, CreateView):
    model = Service
    fields = ["date", "service_type", "occasion"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["term"] = get_object_or_404(Term, pk=self.kwargs["term_pk"])
        return context

    def form_valid(self, form):
        form.instance.term = get_object_or_404(Term, pk=self.kwargs["term_pk"])
        return super().form_valid(form)


class ServiceDetailView(LoginRequiredMixin, DetailView):
    model = Service

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["roles"] = self.object.roles.prefetch_related("pieces__score")
        context["role_form"] = ServiceRoleForm()
        context["piece_form"] = RolePieceForm()
        return context


class ServiceUpdateView(ConductorRequiredMixin, UpdateView):
    model = Service
    fields = ServiceCreateView.fields


class ServiceDeleteView(ConductorRequiredMixin, DeleteView):
    model = Service

    def get_success_url(self):
        return self.object.term.get_absolute_url()


# --- Role / Piece action views ---


@login_required
@user_passes_test(is_conductor)
@require_POST
def add_role(request, service_pk):
    service = get_object_or_404(Service, pk=service_pk)
    form = ServiceRoleForm(request.POST)
    if form.is_valid():
        role = form.save(commit=False)
        role.service = service
        role.save()
    return redirect(service.get_absolute_url())


@login_required
@user_passes_test(is_conductor)
@require_POST
def add_piece(request, role_pk):
    role = get_object_or_404(ServiceRole, pk=role_pk)
    form = RolePieceForm(request.POST)
    if form.is_valid():
        piece = form.save(commit=False)
        piece.service_role = role
        piece.save()
    return redirect(role.service.get_absolute_url())


@login_required
@user_passes_test(is_conductor)
@require_POST
def toggle_confirm(request, piece_pk):
    piece = get_object_or_404(RolePiece, pk=piece_pk)
    piece.is_confirmed = not piece.is_confirmed
    piece.save()
    return redirect(piece.service_role.service.get_absolute_url())
