from django.conf import settings
from django.contrib.auth import login
from django.shortcuts import redirect
from django.views.generic import CreateView

from .forms import SignUpForm


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
