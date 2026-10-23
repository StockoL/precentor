from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from collections import Counter

from django.contrib.contenttypes.models import ContentType
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from accounts.decorators import role_required
from accounts.mixins import OrganisationCreateMixin, OrganisationScopedMixin, RoleRequiredMixin
from accounts.permissions import can_plan
from accounts.querysets import own
from comments.forms import CommentForm
from comments.models import Comment
from comments.utils import attach_reply_forms
from core.models import SiteConfig
from precentor_project.mixins import DeletePageMixin
from precentor_project.utils import ajax_or_redirect

from .forms import (
    RolePieceForm,
    ServiceForm,
    ServiceRoleForm,
    SlotTemplateForm,
    TermForm,
    TermMarkerForm,
)
from .models import RolePiece, Service, ServiceRole, SlotTemplate, Term, TermMarker


class PlanningRequiredMixin(RoleRequiredMixin):
    """For the pages that change a term, service, notice or template."""

    permission = can_plan


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


class TermListView(LoginRequiredMixin, OrganisationScopedMixin, ListView):
    model = Term
    context_object_name = "terms"
    template_name = "planning/term_list.html"

    def get_queryset(self):
        # Every term's services, slots and pieces in a fixed number of
        # queries, however many there are.
        return super().get_queryset().prefetch_related(services_prefetch())

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


class TermDetailView(LoginRequiredMixin, OrganisationScopedMixin, DetailView):
    model = Term

    def get_queryset(self):
        return super().get_queryset().prefetch_related(services_prefetch())

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


class TermCreateView(PlanningRequiredMixin, OrganisationCreateMixin, CreateView):
    model = Term
    form_class = TermForm


class TermUpdateView(PlanningRequiredMixin, OrganisationScopedMixin, UpdateView):
    model = Term
    form_class = TermForm


class TermDeleteView(PlanningRequiredMixin, OrganisationScopedMixin, DeletePageMixin, DeleteView):
    model = Term
    success_url = reverse_lazy("planning:term_list")
    gone_url = success_url
    gone_message = "That term has already been deleted."


# --- Service views ---


class ServiceCreateView(PlanningRequiredMixin, CreateView):
    model = Service
    form_class = ServiceForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["term"] = get_object_or_404(own(Term, self.request), pk=self.kwargs["term_pk"])
        # The suggestions use the church's national calendar.
        context["site_config"] = SiteConfig.get_solo()
        return context

    def get_form_kwargs(self):
        # The new service belongs to the term from the start, so the form
        # can name the term's calendar.
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = Service(term=get_object_or_404(own(Term, self.request), pk=self.kwargs["term_pk"]))
        return kwargs


class ServiceDetailView(LoginRequiredMixin, OrganisationScopedMixin, DetailView):
    model = Service
    # The slots and pieces come with the service, so the status badge and
    # every slot read the same rows: a fixed number of queries however
    # many slots there are.
    queryset = Service.objects.select_related("term", "occasion__season").prefetch_related(
        "roles__pieces__score"
    )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["roles"] = self.object.roles.all()
        # One list for every slot's search box, sent once as JSON, in the
        # ranked order (score-picker.js).
        context["score_options"] = [
            {"value": str(score.pk), "label": str(score)}
            for score in self.object.suggested_scores()
        ]
        context["role_form"] = ServiceRoleForm()
        # Each template knows whether using it would replace the slots, so
        # its button can ask first (service-detail.js).
        has_slots = bool(self.object.roles.all())
        templates = list(SlotTemplate.objects.for_organisation(self.request.organisation))
        for template in templates:
            template.replaces_slots = has_slots and self.object.slot_template_id != template.pk
        context["slot_templates"] = templates

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


class ServiceUpdateView(PlanningRequiredMixin, OrganisationScopedMixin, UpdateView):
    model = Service
    form_class = ServiceForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["term"] = self.object.term
        context["site_config"] = SiteConfig.get_solo()
        return context


# --- Slot templates ---


class SlotTemplateListView(PlanningRequiredMixin, OrganisationScopedMixin, ListView):
    model = SlotTemplate
    context_object_name = "slot_templates"


class ReturnToServiceMixin:
    """After saving a template, go back to the service it was started
    from (?next=), if that's a page on this site; otherwise to the list."""

    def safe_next(self, value):
        """value if it's a page on this site, else "". The Cancel link uses
        it as an href, so anything else (javascript:, another site) must
        never reach the template."""
        if value and url_has_allowed_host_and_scheme(
            value, allowed_hosts={self.request.get_host()}, require_https=self.request.is_secure()
        ):
            return value
        return ""

    def get_success_url(self):
        next_url = self.safe_next(self.request.POST.get("next") or self.request.GET.get("next"))
        return next_url or reverse_lazy("planning:slot_template_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["next"] = self.safe_next(self.request.GET.get("next") or self.request.POST.get("next"))
        return context


class SlotTemplateCreateView(PlanningRequiredMixin, OrganisationCreateMixin, ReturnToServiceMixin, CreateView):
    model = SlotTemplate
    form_class = SlotTemplateForm


class SlotTemplateUpdateView(PlanningRequiredMixin, OrganisationScopedMixin, ReturnToServiceMixin, UpdateView):
    model = SlotTemplate
    form_class = SlotTemplateForm


class SlotTemplateDeleteView(PlanningRequiredMixin, OrganisationScopedMixin, DeletePageMixin, DeleteView):
    model = SlotTemplate
    success_url = reverse_lazy("planning:slot_template_list")
    gone_url = success_url
    gone_message = "That template has already been deleted."


@role_required(can_plan)
@require_POST
def apply_template(request, service_pk, template_pk):
    """
    Give a service a template's slots, then go back to it with a message
    saying what changed. A service uses one template: the same one again
    only fills in missing slots, but another replaces the slots, so it's
    confirmed first. With JavaScript, a dialog asks and sends replace=1;
    without, this shows a page that asks.
    """
    service = get_object_or_404(own(Service, request), pk=service_pk)
    template = get_object_or_404(own(SlotTemplate, request), pk=template_pk)
    replace = request.POST.get("replace") == "1"
    if service.asks_before_using(template) and not replace:
        return render(request, "planning/apply_template_confirm.html", {
            "service": service,
            "template": template,
            "kept": [r.role_name for r in service.roles.prefetch_related("pieces") if r.pieces.all()],
        })

    result = service.use_template(template, replace=replace)
    added, kept = result["added"], result["kept"]
    if replace:
        text = f"Now using {template.name}: {len(added)} slot{'' if len(added) == 1 else 's'} added."
        if kept:
            text += f" Kept {', '.join(kept)}, which {'has' if len(kept) == 1 else 'have'} pieces proposed."
        messages.success(request, text)
    elif not added:
        messages.info(request, f"The {template.name} slots are all here already.")
    else:
        text = f"Added {len(added)} slot{'' if len(added) == 1 else 's'} from {template.name}."
        if result["already_there"]:
            text += f" {len(result['already_there'])} were here already."
        messages.success(request, text)
    return redirect(service.get_absolute_url())


class ServiceDeleteView(PlanningRequiredMixin, OrganisationScopedMixin, DeletePageMixin, DeleteView):
    model = Service
    gone_url = reverse_lazy("planning:term_list")
    gone_message = "That service has already been deleted."

    def get_success_url(self):
        return self.object.term.get_absolute_url()


# --- Role / Piece action views ---


@role_required(can_plan)
@require_POST
def add_role(request, service_pk):
    service = get_object_or_404(own(Service, request), pk=service_pk)
    form = ServiceRoleForm(request.POST)

    if form.is_valid():
        role = form.save(commit=False)
        role.service = service
        role.save()
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


def _slots_fragment(request, service):
    """The service's slot list, redrawn after a slot moves or goes."""
    roles = service.roles.prefetch_related("pieces__score")
    return {
        "roles-list": render_to_string(
            "planning/_roles_list.html", {"roles": roles, "service": service}, request=request
        ),
    }


@role_required(can_plan)
@require_POST
def move_slot(request, role_pk):
    """Move a slot up or down one place (the Move up and Move down
    buttons, which work without JavaScript)."""
    role = get_object_or_404(own(ServiceRole, request).select_related("service"), pk=role_pk)
    step = -1 if request.POST.get("direction") == "up" else 1
    role.service.move_slot(role, step)
    return ajax_or_redirect(request, _slots_fragment(request, role.service), role.service.get_absolute_url())


@role_required(can_plan)
@require_POST
def remove_slot(request, role_pk):
    """Remove a slot. An empty one goes at once; one with pieces proposed
    asks first, in a dialog with JavaScript or on a page without, and is
    removed when the answer comes back with confirm=1."""
    role = get_object_or_404(own(ServiceRole, request).select_related("service"), pk=role_pk)
    service = role.service
    if role.pieces.exists() and not request.POST.get("confirm"):
        return render(request, "planning/remove_slot_confirm.html", {"role": role, "service": service})
    name = role.role_name
    role.delete()
    if request.headers.get("X-Requested-With") != "XMLHttpRequest":
        messages.success(request, f"Removed {name}.")
    return ajax_or_redirect(request, _slots_fragment(request, service), service.get_absolute_url())


@role_required(can_plan)
@require_POST
def reorder_slots(request, service_pk):
    """Put the slots in a new order, sent after a drag as "id,id,id"."""
    service = get_object_or_404(own(Service, request), pk=service_pk)
    try:
        pks = [int(pk) for pk in request.POST.get("order", "").split(",") if pk]
        service.set_slot_order(pks)
    except ValueError:
        return ajax_or_redirect(
            request, _slots_fragment(request, service), service.get_absolute_url(),
            error_message="Couldn't move those slots; the page was out of date.", status=400,
        )
    return ajax_or_redirect(request, _slots_fragment(request, service), service.get_absolute_url())


@role_required(can_plan)
def add_piece(request, role_pk):
    """
    With JavaScript, the service page posts here from each slot's
    combobox. Without it, each slot links here instead: a page with one
    ranked list of scores, so the service page never has to carry a full
    <select> per slot.
    """
    role = get_object_or_404(own(ServiceRole, request).select_related("service"), pk=role_pk)
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    if request.method != "POST":
        form = RolePieceForm(service=role.service)
        return render(request, "planning/add_piece.html", {"role": role, "form": form})

    form = RolePieceForm(request.POST, service=role.service)

    if not form.is_valid() and not is_ajax:
        return render(request, "planning/add_piece.html", {"role": role, "form": form})

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
    return ajax_or_redirect(request, fragments, role.service.get_absolute_url(), status=400)


@role_required(can_plan)
@require_POST
def toggle_confirm(request, piece_pk):
    piece = get_object_or_404(own(RolePiece, request), pk=piece_pk)
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
    term = get_object_or_404(own(Term, request), pk=term_pk)
    draft = request.GET.get("draft") == "1"
    site_config = SiteConfig.of(request.organisation)

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


class TermMarkerCreateView(PlanningRequiredMixin, CreateView):
    model = TermMarker
    form_class = TermMarkerForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["term"] = get_object_or_404(own(Term, self.request), pk=self.kwargs["term_pk"])
        return context

    def form_valid(self, form):
        form.instance.term = get_object_or_404(own(Term, self.request), pk=self.kwargs["term_pk"])
        return super().form_valid(form)

    def get_success_url(self):
        return self.object.term.get_absolute_url()


class TermMarkerUpdateView(PlanningRequiredMixin, OrganisationScopedMixin, UpdateView):
    model = TermMarker
    form_class = TermMarkerForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["term"] = self.object.term
        return context

    def get_success_url(self):
        return self.object.term.get_absolute_url()


class TermMarkerDeleteView(PlanningRequiredMixin, OrganisationScopedMixin, DeletePageMixin, DeleteView):
    model = TermMarker
    gone_url = reverse_lazy("planning:term_list")
    gone_message = "That notice has already been deleted."

    def get_success_url(self):
        return self.object.term.get_absolute_url()
