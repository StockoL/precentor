from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from accounts.mixins import ConductorRequiredMixin
from comments.forms import CommentForm
from comments.utils import attach_reply_forms
from library.models import Score
from precentor_project.utils import ajax_or_redirect

from .forms import (
    RolePieceForm,
    ServiceForm,
    ServiceRoleForm,
    TermForm,
    TermMarkerForm,
)
from .models import RolePiece, Service, ServiceRole, Term, TermMarker

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
        context["markers"] = self.object.markers.all()
        context["content_type_id"] = ContentType.objects.get_for_model(Term).id
        context["comments"] = attach_reply_forms(
            self.object.comments.filter(parent__isnull=True).order_by("created_at")
        )
        context["comment_form"] = CommentForm()
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
        occasion = self.object.occasion
        season = occasion.season if occasion else None
        ranked_scores = Score.objects.ranked_by_suitability(
            occasion=occasion, season=season
        )

        roles = list(self.object.roles.prefetch_related("pieces__score"))
        for role in roles:
            # Each role renders its own propose-piece form on the same page,
            # so each needs a distinct auto_id — Django's default auto_id
            # ("id_score") would otherwise be duplicated once per role,
            # which is invalid HTML and breaks getElementById-based lookups.
            role.piece_form = RolePieceForm(auto_id=f"id_role_{role.pk}_%s")
            # Suited-first ordering is felt here, not just stored — the
            # combobox's option order comes straight from this queryset.
            role.piece_form.fields["score"].queryset = ranked_scores
        context["roles"] = roles
        context["role_form"] = ServiceRoleForm()
        context["content_type_id"] = ContentType.objects.get_for_model(Service).id
        context["comments"] = attach_reply_forms(
            self.object.comments.filter(parent__isnull=True).order_by("created_at")
        )
        context["comment_form"] = CommentForm()
        return context


class ServiceUpdateView(ConductorRequiredMixin, UpdateView):
    model = Service
    form_class = ServiceForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["term"] = self.object.term
        return context


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
        role.piece_form = RolePieceForm(auto_id=f"id_role_{role.pk}_%s")
        fragments = {
            f"role-block-{role.pk}": render_to_string(
                "planning/_role_block.html", {"role": role}, request=request
            ),
            "service-status-badge": render_to_string(
                "planning/_service_status_badge.html", {"service": service}, request=request
            ),
        }
        return ajax_or_redirect(request, fragments, service.get_absolute_url())

    fragments = {
        "add-role-form": render_to_string(
            "planning/_add_role_form.html", {"service": service, "form": form}, request=request
        ),
    }
    return ajax_or_redirect(
        request, fragments, service.get_absolute_url(),
        error_message="Couldn't add that role — please check the form.", status=400,
    )


@login_required
@user_passes_test(ConductorRequiredMixin.is_conductor)
@require_POST
def add_piece(request, role_pk):
    role = get_object_or_404(ServiceRole, pk=role_pk)
    form = RolePieceForm(request.POST, auto_id=f"id_role_{role.pk}_%s")

    if form.is_valid():
        piece = form.save(commit=False)
        piece.service_role = role
        piece.save()
        fragments = {
            f"piece-row-{piece.pk}": render_to_string(
                "planning/_piece_row.html", {"piece": piece}, request=request
            ),
        }
        return ajax_or_redirect(request, fragments, role.service.get_absolute_url())

    fragments = {
        f"add-piece-form-{role.pk}": render_to_string(
            "planning/_add_piece_form.html", {"role": role, "form": form}, request=request
        ),
    }
    return ajax_or_redirect(
        request, fragments, role.service.get_absolute_url(),
        error_message="Couldn't add that piece — please check the form.", status=400,
    )


@login_required
@user_passes_test(ConductorRequiredMixin.is_conductor)
@require_POST
def toggle_confirm(request, piece_pk):
    piece = get_object_or_404(RolePiece, pk=piece_pk)
    piece.is_confirmed = not piece.is_confirmed
    piece.save()

    service = piece.service_role.service
    fragments = {
        f"piece-row-{piece.pk}": render_to_string(
            "planning/_piece_row.html", {"piece": piece}, request=request
        ),
        "service-status-badge": render_to_string(
            "planning/_service_status_badge.html", {"service": service}, request=request
        ),
    }
    return ajax_or_redirect(request, fragments, service.get_absolute_url())


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


# --- TermMarker views ---


class TermMarkerCreateView(ConductorRequiredMixin, CreateView):
    model = TermMarker
    form_class = TermMarkerForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["term"] = get_object_or_404(Term, pk=self.kwargs["term_pk"])
        return context

    def form_valid(self, form):
        form.instance.term = get_object_or_404(Term, pk=self.kwargs["term_pk"])
        return super().form_valid(form)

    def get_success_url(self):
        return self.object.term.get_absolute_url()


class TermMarkerUpdateView(ConductorRequiredMixin, UpdateView):
    model = TermMarker
    form_class = TermMarkerForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["term"] = self.object.term
        return context

    def get_success_url(self):
        return self.object.term.get_absolute_url()


class TermMarkerDeleteView(ConductorRequiredMixin, DeleteView):
    model = TermMarker

    def get_success_url(self):
        return self.object.term.get_absolute_url()
