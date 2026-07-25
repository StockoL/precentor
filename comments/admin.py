from django.contrib import admin

from .models import Comment


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ["author", "target", "display_state", "created_at"]  # noqa
    list_filter = ["is_open"]  # noqa

    def display_state(self, obj):
        return obj.state

    display_state.short_description = "State"
