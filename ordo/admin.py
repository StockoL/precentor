from django.contrib import admin

from .models import LiturgicalOccasion, LiturgicalSeason, UseType


@admin.register(LiturgicalOccasion)
class LiturgicalOccasionAdmin(admin.ModelAdmin):
    list_display = ["name", "calendar_use", "season", "colour", "is_moveable"]  # noqa
    list_filter = ["calendar_use", "season", "colour", "is_moveable"]  # noqa
    search_fields = ["name"]  # noqa


@admin.register(LiturgicalSeason)
class LiturgicalSeasonAdmin(admin.ModelAdmin):
    list_display = ["name"]  # noqa


@admin.register(UseType)
class UseTypeAdmin(admin.ModelAdmin):
    list_display = ["name"]  # noqa
