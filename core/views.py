from django.http import Http404, HttpResponse
from django.urls import reverse_lazy
from django.views.decorators.http import require_safe
from django.views.generic import UpdateView

from accounts.mixins import RoleRequiredMixin
from accounts.permissions import can_manage_settings

from .forms import SiteConfigForm
from .imaging import TARGET_SIZE
from .models import SiteConfig


class SiteConfigUpdateView(RoleRequiredMixin, UpdateView):
    permission = can_manage_settings
    model = SiteConfig
    form_class = SiteConfigForm
    template_name = "core/site_config_form.html"
    success_url = reverse_lazy("core:site_config_update")

    def get_object(self, queryset=None):
        return SiteConfig.of(self.request.organisation)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["site_config"] = self.object
        context["banner_size"] = TARGET_SIZE
        return context


@require_safe
def crest(request, organisation_pk, version):
    """
    A church's crest, from the database. It's public branding, printed at
    the top of the music list, so it needs no login; the address names the
    church. The version in the address is a fingerprint of the image, so
    browsers can keep it for a year: a new crest gets a new address, and an
    old address finds nothing.
    """
    config = SiteConfig.objects.filter(organisation_id=organisation_pk).first()
    if config is None or not config.has_crest or version != config.crest_version:
        raise Http404("No crest at this address.")
    response = HttpResponse(bytes(config.crest), content_type=config.crest_type)
    response["Cache-Control"] = "public, max-age=31536000, immutable"
    return response
