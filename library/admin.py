from django.contrib import admin

from .models import Score


@admin.register(Score)
class ScoreAdmin(admin.ModelAdmin):
    list_display = ["title", "composer", "voicing", "language", "copies_owned"]  # noqa (Django Meta, not a normal class — no shared-state risk)
    search_fields = ["title", "composer_surname", "composer_other_names"]  # noqa (Django Meta, not a normal class — no shared-state risk)
    list_filter = ["language"]  # noqa (Django Meta, not a normal class — no shared-state risk)
