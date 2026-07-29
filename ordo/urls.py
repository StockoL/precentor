from django.urls import path

from . import views

app_name = "ordo"

urlpatterns = [
    path("occasion-lookup/", views.occasion_lookup, name="occasion_lookup"),
]
