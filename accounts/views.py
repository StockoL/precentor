from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, FormView, ListView

from precentor_project.mixins import DeletePageMixin

from .decorators import role_required
from .forms import InvitationForm, JoinForm, RoleForm, SignUpForm
from .mixins import OrganisationScopedMixin, RoleRequiredMixin
from .models import Invitation, User
from .permissions import can_manage_organisation


def members_of(request):
    """The active people in the signed-in person's church. A superuser
    belongs to none, so has nobody (filtering on an empty organisation
    would find the superusers)."""
    if request.organisation is None:
        return User.objects.none()
    return User.objects.filter(organisation=request.organisation, is_active=True)


# Where a new invitation's secret waits in the owner's session between
# making it and seeing its link, which happens once.
NEW_INVITATION = "new_invitation"


class SignUpView(CreateView):
    """Register a church: its first person is signed straight in."""

    form_class = SignUpForm
    template_name = "registration/signup.html"

    def dispatch(self, request, *args, **kwargs):
        # Someone signed in already has a church.
        if request.user.is_authenticated:
            return redirect(settings.LOGIN_REDIRECT_URL)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        login(self.request, form.save())
        return redirect(settings.LOGIN_REDIRECT_URL)


class JoinView(FormView):
    """
    Accept an invitation. Every link that no longer works, whether used,
    expired, cancelled or mistyped, gets the same page, so nobody learns
    which of those it was.
    """

    form_class = JoinForm
    template_name = "registration/join.html"

    def dispatch(self, request, *args, **kwargs):
        # One church per person, so someone signed in can't take a place.
        if request.user.is_authenticated:
            return render(request, "registration/join_signed_in.html")
        self.invitation = Invitation.find(kwargs["token"])
        if self.invitation is None:
            return self.gone()
        return super().dispatch(request, *args, **kwargs)

    def gone(self):
        return render(self.request, "registration/join_gone.html", status=404)

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "invitation": self.invitation}

    def get_context_data(self, **kwargs):
        return super().get_context_data(invitation=self.invitation, **kwargs)

    def form_valid(self, form):
        try:
            user = form.save()
        except Invitation.Gone:
            return self.gone()
        login(self.request, user)
        return redirect(settings.LOGIN_REDIRECT_URL)


class InvitationCreateView(RoleRequiredMixin, FormView):
    """The owner invites someone. The link is shown on the next page, after
    a redirect, so refreshing can't quietly make a second invitation."""

    permission = can_manage_organisation
    form_class = InvitationForm
    template_name = "accounts/invitation_form.html"

    def form_valid(self, form):
        invitation, token = Invitation.make(
            organisation=self.request.organisation,
            role=form.cleaned_data["role"],
            note=form.cleaned_data["note"],
            created_by=self.request.user,
        )
        self.request.session[NEW_INVITATION] = {"pk": invitation.pk, "token": token}
        return redirect("members:invitation_link", pk=invitation.pk)


class InvitationLinkView(RoleRequiredMixin, OrganisationScopedMixin, DetailView):
    """Shows a new invitation's link, once: the secret leaves the session as
    it's shown, and only its fingerprint is kept anywhere."""

    permission = can_manage_organisation
    model = Invitation
    context_object_name = "invitation"
    template_name = "accounts/invitation_link.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        waiting = self.request.session.pop(NEW_INVITATION, None)
        if waiting and waiting["pk"] == self.object.pk:
            context["link"] = self.request.build_absolute_uri(reverse("join", args=[waiting["token"]]))
        return context


class MemberListView(LoginRequiredMixin, ListView):
    """
    Who's in the church. Everyone can see names and roles, so it's clear
    who the conductor and librarian are; the owner also sees addresses
    and the invitations still waiting to be used.
    """

    context_object_name = "members"
    template_name = "accounts/member_list.html"

    def get_queryset(self):
        return members_of(self.request).order_by("-is_owner", "name", "email")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if can_manage_organisation(self.request.user):
            for member in context["members"]:
                member.role_form = RoleForm(instance=member, auto_id=f"id_member_{member.pk}_%s")
            context["invitations"] = Invitation.usable().for_organisation(self.request.organisation)
        return context


class InvitationCancelView(RoleRequiredMixin, OrganisationScopedMixin, DeletePageMixin, DeleteView):
    """The owner cancels an invitation, which simply deletes it: its link
    then gets the same "no longer works" page as any other."""

    permission = can_manage_organisation
    model = Invitation
    context_object_name = "invitation"
    template_name = "accounts/invitation_confirm_cancel.html"
    success_url = reverse_lazy("members:member_list")
    gone_url = success_url
    gone_message = "That invitation has already been used or cancelled."

    def get_queryset(self):
        # One that's been used is the record of who joined, so it stays.
        return super().get_queryset().filter(used_at__isnull=True)


@role_required(can_manage_organisation)
@require_POST
def change_role(request, pk):
    member = get_object_or_404(members_of(request), pk=pk)
    form = RoleForm(request.POST, instance=member)
    if form.is_valid():
        form.save()
        messages.success(request, f"{member} is now a {member.get_role_display()}.")
    else:
        messages.error(request, form.errors["role"][0])
    return redirect("members:member_list")
