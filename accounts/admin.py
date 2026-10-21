from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm

from .models import Organisation, User


@admin.register(Organisation)
class OrganisationAdmin(admin.ModelAdmin):
    list_display = ["name", "created_at"]
    search_fields = ["name"]


# Django's user forms name its own User model and a username field, so
# each points at this model, which signs in by email.
class UserCreationForm(AdminUserCreationForm):
    class Meta(AdminUserCreationForm.Meta):
        model = User
        fields = ["email"]


class UserEditForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """Django's user admin, which sets passwords properly, laid out for
    email, organisation and role instead of username and groups."""

    form = UserEditForm
    add_form = UserCreationForm
    list_display = ["email", "name", "organisation", "role", "is_owner", "is_active"]
    list_filter = ["organisation", "role", "is_owner", "is_active", "is_superuser"]
    search_fields = ["email", "name"]
    ordering = ["email"]
    filter_horizontal = []
    fieldsets = [
        (None, {"fields": ["email", "password", "name"]}),
        ("In the app", {"fields": ["organisation", "role", "is_owner"]}),
        ("Site administration", {"fields": ["is_active", "is_staff", "is_superuser"]}),
        ("Dates", {"fields": ["last_login", "date_joined"]}),
    ]
    add_fieldsets = [
        (None, {
            "classes": ["wide"],
            "fields": ["email", "name", "organisation", "role", "usable_password", "password1", "password2"],
        }),
    ]
