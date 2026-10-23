from django.conf import settings
from django.contrib.auth import login
from django.shortcuts import redirect, render
from django.views.generic import CreateView, FormView

from .forms import JoinForm, SignUpForm
from .models import Invitation


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
