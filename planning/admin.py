from django.contrib import admin

from .models import RolePiece, Service, ServiceRole, Term


class ServiceRoleInline(admin.TabularInline):
    model = ServiceRole
    extra = 1


class RolePieceInline(admin.TabularInline):
    model = RolePiece
    extra = 1


@admin.register(Term)
class TermAdmin(admin.ModelAdmin):
    list_display = ["name", "start_date", "end_date"]  # noqa


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ["service_type", "date", "term", "occasion", "display_status"]  # noqa
    list_filter = ["term", "service_type"]  # noqa
    inlines = [ServiceRoleInline]  # noqa

    def display_status(self, obj):
        return obj.status

    display_status.short_description = "Status"


@admin.register(ServiceRole)
class ServiceRoleAdmin(admin.ModelAdmin):
    list_display = ["role_name", "service", "is_not_applicable"]  # noqa
    inlines = [RolePieceInline]  # noqa
