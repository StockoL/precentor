from django.contrib import admin

from .models import LiturgicalOccasion, LiturgicalSeason, UseType


@admin.register(LiturgicalOccasion)
class LiturgicalOccasionAdmin(admin.ModelAdmin):
    list_display = ["name", "calendar_use", "calendar", "rank", "precedence", "colour", "season"]  # noqa
    list_filter = ["calendar_use", "calendar", "rank", "season", "colour"]  # noqa
    search_fields = ["name", "key"]  # noqa


@admin.register(LiturgicalSeason)
class LiturgicalSeasonAdmin(admin.ModelAdmin):
    list_display = ["name"]  # noqa


@admin.register(UseType)
class UseTypeAdmin(admin.ModelAdmin):
    list_display = ["name"]  # noqa
