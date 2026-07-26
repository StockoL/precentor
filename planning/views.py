from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from .forms import RolePieceForm, ServiceForm, ServiceRoleForm, TermForm
from .mixins import ConductorRequiredMixin
from .models import RolePiece, Service, ServiceRole, Term

# --- Term views ---


class TermListView(LoginRequiredMixin, ListView):
    model = Term
    context_object_name = "terms"
    template_name = "planning/term_list.html"

    def get_queryset(self):
        terms = list(super().get_queryset())
        for term in terms:
            term.summary = term.completion_summary()
        return terms


class TermDetailView(LoginRequiredMixin, DetailView):
    model = Term

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["services"] = self.object.services.all()
        context["content_type_id"] = ContentType.objects.get_for_model(Term).id
        context["comments"] = self.object.comments.filter(parent__isnull=True).order_by(
            "created_at"
        )
        return context


class TermCreateView(ConductorRequiredMixin, CreateView):
    model = Term
    form_class = TermForm


class TermUpdateView(ConductorRequiredMixin, UpdateView):
    model = Term
    form_class = TermForm


class TermDeleteView(ConductorRequiredMixin, DeleteView):
    model = Term
    success_url = reverse_lazy("planning:term_list")


# --- Service views ---


class ServiceCreateView(ConductorRequiredMixin, CreateView):
    model = Service
    form_class = ServiceForm

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
        context["content_type_id"] = ContentType.objects.get_for_model(Service).id
        context["comments"] = self.object.comments.filter(parent__isnull=True).order_by(
            "created_at"
        )
        return context


class ServiceUpdateView(ConductorRequiredMixin, UpdateView):
    model = Service
    form_class = ServiceForm


class ServiceDeleteView(ConductorRequiredMixin, DeleteView):
    model = Service

    def get_success_url(self):
        return self.object.term.get_absolute_url()


# --- Role / Piece action views ---


@login_required
@user_passes_test(ConductorRequiredMixin.is_conductor)
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
@user_passes_test(ConductorRequiredMixin.is_conductor)
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
@user_passes_test(ConductorRequiredMixin.is_conductor)
@require_POST
def toggle_confirm(request, piece_pk):
    piece = get_object_or_404(RolePiece, pk=piece_pk)
    piece.is_confirmed = not piece.is_confirmed
    piece.save()
    return redirect(piece.service_role.service.get_absolute_url())


@login_required
def term_music_list(request, term_pk):
    term = get_object_or_404(Term, pk=term_pk)
    draft = request.GET.get("draft") == "1"
    services = term.services.prefetch_related("roles__pieces__score").order_by("date")

    service_rows = [
        {"service": service, "rows": service.music_list_rows(draft=draft)}
        for service in services
    ]

    return render(
        request,
        "planning/music_list.html",
        {
            "term": term,
            "service_rows": service_rows,
            "draft": draft,
        },
    )
