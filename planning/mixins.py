from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin


class ConductorRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    @staticmethod
    def is_conductor(user):
        return user.is_superuser or user.groups.filter(name="Conductor").exists()

    def test_func(self):
        return self.is_conductor(self.request.user)
