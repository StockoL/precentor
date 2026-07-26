from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin


class ConductorRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.groups.filter(name="Conductor").exists()
