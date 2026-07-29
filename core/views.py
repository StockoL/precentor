from django.urls import reverse_lazy
from django.views.generic import UpdateView

from accounts.mixins import ConductorRequiredMixin

from .forms import SiteConfigForm
from .models import SiteConfig


class SiteConfigUpdateView(ConductorRequiredMixin, UpdateView):
    model = SiteConfig
    form_class = SiteConfigForm
    template_name = "core/site_config_form.html"
    success_url = reverse_lazy("core:site_config_update")

    def get_object(self, queryset=None):
        return SiteConfig.get_solo()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["site_config"] = self.object
        return context
