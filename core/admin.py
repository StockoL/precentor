from django.contrib import admin

from .models import SiteConfig


@admin.register(SiteConfig)
class SiteConfigAdmin(admin.ModelAdmin):
    # One row per church: the database refuses a second for the same one.
    list_display = ["organisation", "church_name", "layout_style", "show_hymns_psalm"]  # noqa

    def has_delete_permission(self, request, obj=None):
        return False
