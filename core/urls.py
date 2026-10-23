from django.urls import path

from . import views

app_name = "core"
urlpatterns = [
    path("", views.SiteConfigUpdateView.as_view(), name="site_config_update"),
    path("crest/<int:organisation_pk>/<str:version>/", views.crest, name="crest"),
]
