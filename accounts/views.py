from django.conf import settings
from django.contrib.auth import login
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.generic import CreateView, DetailView, FormView

from .forms import InvitationForm, JoinForm, SignUpForm
from .mixins import OrganisationScopedMixin, RoleRequiredMixin
from .models import Invitation
from .permissions import can_manage_organisation

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
