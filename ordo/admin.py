from django.contrib import admin

from .models import LiturgicalOccasion


@admin.register(LiturgicalOccasion)
class LiturgicalOccasionAdmin(admin.ModelAdmin):
    list_display = ["name", "tradition", "colour", "is_moveable"]  # noqa
    list_filter = ["tradition", "colour", "is_moveable"]  # noqa
    search_fields = ["name"]  # noqa
