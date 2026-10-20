from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin
from collections import Counter

from django.contrib.contenttypes.models import ContentType
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.utils import timezone
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
from comments.models import Comment
from comments.utils import attach_reply_forms
from core.models import SiteConfig
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

# A service this close is flagged if it still has slots to settle.
SOON_DAYS = 14


def services_prefetch():
    """
    A term's services in date order, with their slots, pieces and
    occasion loaded alongside. Service.status, unsettled_slots and
    ServiceRole.is_resolved read these prefetched rows, so a page of
    services costs a fixed number of queries rather than several each.
    """
    return Prefetch(
        "services",
        queryset=Service.objects.order_by("date")
        .select_related("occasion")
        .prefetch_related("roles__pieces"),
    )


def describe_term(term, today):
    """
    Set the attributes a term's status display reads: phase and timing,
    counts by status, readiness, and the next service with what it still
    needs. Shared by the Terms page and the term page; expects the term's
    services prefetched with services_prefetch().
    """
    services = list(term.services.all())
    statuses = Counter(service.status for service in services)
    term.card_phase = term.phase(today)
    term.card_phase_label = term.phase_label(today)
    term.card_timing = term.timing_label(today)
    term.summary = {
        "total": len(services),
        "complete": statuses["complete"],
        "in_progress": statuses["in_progress"],
        "not_started": statuses["not_started"],
    }
    term.ready_to_publish = bool(services) and statuses["complete"] == len(services)
    term.next_service = next((s for s in services if s.date >= today), None)
    if term.next_service:
        term.outstanding = term.next_service.unsettled_slots
        term.next_is_soon = (term.next_service.date - today).days <= SOON_DAYS


class TermListView(LoginRequiredMixin, ListView):
    model = Term
    context_object_name = "terms"
    template_name = "planning/term_list.html"

    def get_queryset(self):
        # Every term's services, slots and pieces in a fixed number of
        # queries, however many there are.
        return Term.objects.prefetch_related(services_prefetch())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        terms = list(context["terms"])
        open_comments = self.open_comment_counts(terms)

        for term in terms:
            describe_term(term, today)
            term.open_comments = open_comments[term.pk]

        # Current and upcoming terms first, soonest first; past terms
        # after, most recent first, folded away in the template.
        context["active_terms"] = sorted(
            (t for t in terms if t.card_phase != "past"), key=lambda t: t.start_date
        )
        context["past_terms"] = sorted(
            (t for t in terms if t.card_phase == "past"),
            key=lambda t: t.start_date,
            reverse=True,
        )
        return context

    @staticmethod
    def open_comment_counts(terms):
        """
        Open comments per term, counting those on the term, on its
        services and on their pieces. Three queries in all, one per kind
        of target, matched to terms using the prefetched services.
        """
        term_of_service = {}
        term_of_piece = {}
        for term in terms:
            for service in term.services.all():
                term_of_service[service.pk] = term.pk
                for role in service.roles.all():
                    for piece in role.pieces.all():
                        term_of_piece[piece.pk] = term.pk

        def open_on(model, pks):
            return Comment.objects.filter(
                is_open=True,
                content_type=ContentType.objects.get_for_model(model),
                object_id__in=pks,
            ).values_list("object_id", flat=True)

        counts = Counter()
        counts.update(open_on(Term, [term.pk for term in terms]))
        counts.update(term_of_service[pk] for pk in open_on(Service, term_of_service))
        counts.update(term_of_piece[pk] for pk in open_on(RolePiece, term_of_piece))
        return counts


class TermDetailView(LoginRequiredMixin, DetailView):
    model = Term

    def get_queryset(self):
        return Term.objects.prefetch_related(services_prefetch())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        describe_term(self.object, timezone.localdate())
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

        # The services either side of this one in its term, for Previous
        # and Next links. Date, then id, so two services on one day keep a
        # fixed order.
        siblings = list(
            self.object.term.services.order_by("date", "pk").only("pk", "date", "service_type")
        )
        position = next(i for i, s in enumerate(siblings) if s.pk == self.object.pk)
        context["previous_service"] = siblings[position - 1] if position > 0 else None
        context["next_service"] = siblings[position + 1] if position + 1 < len(siblings) else None

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
        error_message="Couldn't add that slot — please check the form.", status=400,
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
    site_config = SiteConfig.get_solo()

    services = (
        term.services.select_related("occasion")
        .prefetch_related("roles__pieces__score", "additional_occasions")
        .order_by("date")
    )
    markers = term.markers.order_by("date")

    entries = [
        {
            "type": "service",
            "date": service.date,
            "service": service,
            "rows": service.music_list_rows(draft=draft),
        }
        for service in services
    ] + [
        {"type": "marker", "date": marker.date, "marker": marker}
        for marker in markers
    ]
    # Stable secondary key so same-day ties are deterministic: a service
    # sharing a date with a marker always renders service-then-marker.
    entries.sort(key=lambda entry: (entry["date"], 0 if entry["type"] == "service" else 1))

    return render(
        request,
        "planning/music_list.html",
        {
            "term": term,
            "entries": entries,
            "draft": draft,
            "site_config": site_config,
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
