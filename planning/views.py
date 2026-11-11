from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from collections import Counter

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Prefetch
from django.http import Http404, JsonResponse
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

from accounts.decorators import role_required
from accounts.mixins import OrganisationCreateMixin, OrganisationScopedMixin, RoleRequiredMixin
from accounts.permissions import can_plan
from accounts.querysets import own
from comments.forms import CommentForm
from comments.models import Comment
from comments.utils import attach_reply_forms
from core.models import SiteConfig
from library.models import Score
from ordo.models import UseType
from precentor_project.mixins import DeletePageMixin
from precentor_project.utils import ajax_or_redirect, safe_next

from .forms import (
    RolePieceForm,
    ServiceForm,
    ServiceRoleForm,
    SlotTemplateForm,
    TemplateSlotFormSet,
    TermForm,
    TermMarkerForm,
)
from .models import RolePiece, Service, ServiceRole, SlotTemplate, Term, TermMarker
from .suggestions import page_options, slot_use_type


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
        # A church with no terms and no music yet gets a few first steps
        # instead; they go of their own accord once there's something.
        context["getting_started"] = not terms and not own(Score, self.request).exists()
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
        context["site_config"] = SiteConfig.of(self.request.organisation)
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
        "roles__pieces__score", "roles__pieces__tune", "roles__pieces__hymn_entry__hymnal",
        "roles__pieces__hymn_entry__hymn", "roles__pieces__hymn_entry__tune", "roles__pieces__comments",
    )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["roles"] = self.object.roles.all()
        # One list for every slot's search box, sent once as JSON with what
        # each suggestion rests on, and the church's use types, which
        # score-picker.js matches to each slot (planning/suggestions.py).
        window = SiteConfig.of(self.request.organisation).repeat_window_weeks
        context["score_options"] = page_options(self.object, window)
        context["use_type_options"] = [
            {"id": use_type.pk, "name": use_type.name}
            for use_type in UseType.objects.for_organisation(self.request.organisation)
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
        context["site_config"] = SiteConfig.of(self.request.organisation)
        return context


# --- Slot templates ---


class SlotTemplateListView(PlanningRequiredMixin, OrganisationScopedMixin, ListView):
    model = SlotTemplate
    context_object_name = "slot_templates"


class ReturnToServiceMixin:
    """After saving a template, go back to the service it was started
    from (?next=), if that's a page on this site; otherwise to the list."""

    def get_success_url(self):
        next_url = safe_next(self.request, self.request.POST.get("next") or self.request.GET.get("next"))
        return next_url or reverse_lazy("planning:slot_template_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["next"] = safe_next(self.request, self.request.GET.get("next") or self.request.POST.get("next"))
        return context


class TemplateSlotsMixin:
    """A template's slots as a formset beside its name: both are checked,
    and both are saved together or not at all."""

    def slots_formset(self, instance):
        data = self.request.POST if self.request.method == "POST" else None
        return TemplateSlotFormSet(data, instance=instance, prefix="slots")

    def get_context_data(self, **kwargs):
        if "slots_formset" not in kwargs:
            kwargs["slots_formset"] = self.slots_formset(self.object or SlotTemplate())
        return super().get_context_data(**kwargs)

    def form_valid(self, form):
        formset = self.slots_formset(form.instance)
        if not formset.is_valid():
            return self.render_to_response(self.get_context_data(form=form, slots_formset=formset))
        with transaction.atomic():
            response = super().form_valid(form)
            formset.instance = self.object
            formset.save_slots()
        return response

    def form_invalid(self, form):
        formset = self.slots_formset(form.instance)
        formset.is_valid()  # so its own errors show too
        return self.render_to_response(self.get_context_data(form=form, slots_formset=formset))


class SlotTemplateCreateView(
    PlanningRequiredMixin, OrganisationCreateMixin, ReturnToServiceMixin, TemplateSlotsMixin, CreateView
):
    model = SlotTemplate
    form_class = SlotTemplateForm


class SlotTemplateUpdateView(
    PlanningRequiredMixin, OrganisationScopedMixin, ReturnToServiceMixin, TemplateSlotsMixin, UpdateView
):
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
        error_message="Couldn't add that slot. Please check the form.", status=400,
    )


def _slots_fragment(request, service):
    """The service's slot list, redrawn after a slot moves or goes."""
    roles = service.roles.prefetch_related(
        "pieces__score", "pieces__tune", "pieces__hymn_entry__hymnal", "pieces__hymn_entry__hymn",
        "pieces__hymn_entry__tune", "pieces__comments",
    )
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
def change_kind(request, role_pk):
    """Change how a slot is shown and grouped, such as an Introit sung as
    a hymn. Its proper part stays, as it's still the Introit."""
    role = get_object_or_404(own(ServiceRole, request).select_related("service"), pk=role_pk)
    kind = request.POST.get("kind")
    url = role.service.get_absolute_url()
    if kind not in dict(ServiceRole.KINDS):
        return ajax_or_redirect(request, {}, url, error_message="Choose one of the kinds listed.", status=400)
    role.kind = kind
    role.save(update_fields=["kind"])
    if request.headers.get("X-Requested-With") != "XMLHttpRequest":
        messages.success(request, f"The {role.role_name} is now shown as {role.get_kind_display()}.")
    badge = render_to_string("planning/_kind_badge.html", {"role": role}, request=request)
    return ajax_or_redirect(request, {f"kind-badge-{role.pk}": badge}, url)


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
    <select> per slot. "Propose and confirm" sends confirm=1, and the
    piece is saved confirmed; the service's status badge is sent back
    with it then, as it may have changed, just as toggle_confirm does.
    """
    role = get_object_or_404(own(ServiceRole, request).select_related("service"), pk=role_pk)
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    if request.method != "POST":
        form = RolePieceForm(role=role)
        form.show_suggestions()
        return render(request, "planning/add_piece.html", {"role": role, "form": form})

    form = RolePieceForm(request.POST, role=role)

    if not form.is_valid() and not is_ajax:
        form.show_suggestions()
        return render(request, "planning/add_piece.html", {"role": role, "form": form})

    if form.is_valid():
        piece = form.save(commit=False)
        piece.service_role = role
        piece.is_confirmed = request.POST.get("confirm") == "1"
        piece.save()
        fragments = {
            f"piece-row-{piece.pk}": render_to_string(
                "planning/_piece_row.html", {"piece": piece}, request=request
            ),
        }
        if piece.is_confirmed:
            fragments["service-status-badge"] = render_to_string(
                "planning/_service_status_badge.html", {"service": role.service}, request=request
            )
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
    """
    Confirm or unconfirm a piece. The button sends the state it asks for,
    so the same request twice, from a double click, leaves the piece as
    asked rather than turning it back. A page opened before the button
    sent it posts nothing, and toggles as it always did.
    """
    piece = get_object_or_404(own(RolePiece, request), pk=piece_pk)
    wanted = request.POST.get("confirmed")
    piece.is_confirmed = wanted == "1" if wanted in ("0", "1") else not piece.is_confirmed
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


@role_required(can_plan)
def remove_piece(request, piece_pk):
    """
    Take a piece out of its slot. One that's only proposed, with no
    comments, goes at once; one that would lose something (its place on
    the music list, or comments) asks first, in a dialog with JavaScript
    or on this page without, and goes when the answer comes back with
    confirm=1. Only a POST removes anything.

    A piece already gone (Back, or a second click) can't say which service
    it was on, so the form sends the service's address as next, and the
    person goes back there with a message rather than "not found". With
    JavaScript the message waits for the reload the script then does.
    """
    next_url = safe_next(request, request.POST.get("next") or request.GET.get("next"))
    piece = own(RolePiece, request).select_related("service_role__service").filter(pk=piece_pk).first()
    if piece is None:
        messages.info(request, "That piece has already been removed.")
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"fragments": {}}, status=410)
        return redirect(next_url or "planning:term_list")
    role = piece.service_role
    service = role.service
    if request.method != "POST" or (piece.removal_warnings() and not request.POST.get("confirm")):
        return render(request, "planning/remove_piece_confirm.html", {"piece": piece, "role": role, "service": service})
    title = piece.title
    piece.delete()
    if request.headers.get("X-Requested-With") != "XMLHttpRequest":
        messages.success(request, f"Removed {title} from the {role.role_name}.")
    # The slot's list (with its empty line if that was the last piece), the
    # status, which the pieces decide, and the slot's form, which offers a
    # removed chant again.
    fragments = {
        f"role-{role.pk}-pieces": render_to_string("planning/_role_pieces.html", {"role": role}, request=request),
        "service-status-badge": render_to_string(
            "planning/_service_status_badge.html", {"service": service}, request=request
        ),
        f"add-piece-form-{role.pk}": render_to_string(
            "planning/_add_piece_form.html", {"role": role, "form": RolePieceForm(role=role)}, request=request
        ),
    }
    return ajax_or_redirect(request, fragments, service.get_absolute_url())


def upcoming_services(request, score):
    """
    This church's services from today on, soonest first, for proposing a
    score from its own page: each with its status, and has_score when the
    score is in it already. Both are read from the prefetched slots and
    pieces, as on the Terms page, so a long list costs no more queries.
    """
    services = list(
        own(Service, request).filter(date__gte=timezone.localdate())
        .select_related("term").prefetch_related("roles__pieces").order_by("date", "pk")
    )
    for service in services:
        service.has_score = any(
            piece.score_id == score.pk for role in service.roles.all() for piece in role.pieces.all()
        )
    return services


def slot_choice(service, score):
    """
    The service's slots for the second step, empty ones first and each
    with what it holds, and the slot to start on with the reason shown
    beside it: the one slot named for a use the score is marked for, if
    only one is, or else the first empty slot, or else a new slot.
    """
    slots = list(service.roles.all())
    for slot in slots:
        slot.holds = ", ".join(piece.title for piece in slot.pieces.all()) or "empty"
    empty = [slot for slot in slots if slot.holds == "empty"]
    use_types = UseType.objects.for_organisation(service.organisation_id)
    suited = set(score.suited_use_types.values_list("pk", flat=True))
    matches = [(slot, use) for slot in slots if (use := slot_use_type(slot, use_types)) and use.pk in suited]
    if len(matches) == 1:
        chosen, why = matches[0][0], f"Chosen because this score is marked for {matches[0][1].name}."
    elif empty:
        chosen, why = empty[0], "The first empty slot" + (
            ", as the score is marked for more than one of these slots." if matches else ".")
    else:
        chosen, why = None, "Every slot has something in it; choose one, or add a new slot."
    return empty + [slot for slot in slots if slot not in empty], chosen, why


def proposing_into(request, service_pk):
    """The service chosen in the first step: this church's, or not found."""
    if not str(service_pk).isdigit():
        raise Http404
    return get_object_or_404(
        own(Service, request).select_related("term").prefetch_related(
            "roles__pieces__score", "roles__pieces__hymn_entry__hymnal"),
        pk=service_pk,
    )


@role_required(can_plan)
def propose_score(request, score_pk):
    """
    Propose a score from the library rather than from a service: first
    the service, then the slot. Each step is a page of its own without
    JavaScript. The score is this church's, or not found, and so is the
    service chosen.
    """
    score = get_object_or_404(own(Score, request), pk=score_pk)
    context = {"score": score, "services": upcoming_services(request, score)}
    if request.GET.get("service"):
        service = proposing_into(request, request.GET["service"])
        slots, chosen, why = slot_choice(service, score)
        context.update(service=service, slots=slots, chosen=chosen, why=why)
    return render(request, "planning/propose_score.html", context)


@role_required(can_plan)
@require_POST
def set_tune(request, piece_pk):
    """
    Choose the tune a hymn is sung to here. Only one of the piece's own
    choices is accepted, so never another church's tune; choosing the
    book's usual tune stores nothing, as that's what a hymn is sung to
    unless someone says otherwise.
    """
    piece = get_object_or_404(own(RolePiece, request), pk=piece_pk)
    url = piece.service_role.service.get_absolute_url()
    usual = piece.hymn_entry.tune if piece.hymn_entry_id else None
    allowed = {str(tune.pk): tune for _, tunes in piece.tune_choices() for tune in tunes}
    choice = request.POST.get("tune", "")
    if choice not in allowed:
        return ajax_or_redirect(request, {}, url, error_message="Choose one of the tunes listed.", status=400)
    piece.tune = None if allowed[choice] == usual else allowed[choice]
    piece.save(update_fields=["tune"])
    row = render_to_string("planning/_piece_row.html", {"piece": piece}, request=request)
    fragments = {f"piece-row-{piece.pk}": row}
    return ajax_or_redirect(request, fragments, url)


@login_required
def service_pew_sheet(request, pk):
    """
    A service's sheet for the congregation: its confirmed music in order,
    with motet texts beside their translations. Texts and composers can be
    left off with a plain GET form; both are on until the form is used.
    """
    service = get_object_or_404(
        own(Service, request).select_related("occasion").prefetch_related(
            "roles__pieces__score", "roles__pieces__tune", "roles__pieces__hymn_entry__hymnal",
            "roles__pieces__hymn_entry__tune",
        ),
        pk=pk,
    )
    chosen = "shown" in request.GET
    options = {
        "texts": not chosen or "texts" in request.GET,
        "composers": not chosen or "composers" in request.GET,
    }
    return render(request, "planning/pew_sheet.html", {
        "service": service,
        "rows": service.pew_sheet_rows(),
        "options": options,
        "site_config": SiteConfig.of(request.organisation),
    })


@login_required
def term_music_list(request, term_pk):
    term = get_object_or_404(own(Term, request), pk=term_pk)
    draft = request.GET.get("draft") == "1"
    site_config = SiteConfig.of(request.organisation)

    services = (
        term.services.select_related("occasion")
        .prefetch_related("roles__pieces__score", "roles__pieces__hymn_entry__hymnal", "additional_occasions")
        .order_by("date")
    )
    markers = term.markers.order_by("date")

    entries = [
        {
            "type": "service",
            "date": service.date,
            "service": service,
            "groups": service.music_list_groups(draft=draft, arrangement=site_config.music_list_arrangement),
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
