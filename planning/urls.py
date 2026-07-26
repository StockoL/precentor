from django.urls import path

from . import views

app_name = "planning"

urlpatterns = [
    path("", views.TermListView.as_view(), name="term_list"),
    path("terms/add/", views.TermCreateView.as_view(), name="term_create"),
    path("terms/<int:pk>/edit/", views.TermUpdateView.as_view(), name="term_update"),
    path("terms/<int:pk>/delete/", views.TermDeleteView.as_view(), name="term_delete"),
    path("terms/<int:pk>/", views.TermDetailView.as_view(), name="term_detail"),
    path(
        "terms/<int:term_pk>/services/add/",
        views.ServiceCreateView.as_view(),
        name="service_create",
    ),
    path(
        "services/<int:pk>/", views.ServiceDetailView.as_view(), name="service_detail"
    ),
    path(
        "services/<int:pk>/edit/",
        views.ServiceUpdateView.as_view(),
        name="service_update",
    ),
    path(
        "services/<int:pk>/delete/",
        views.ServiceDeleteView.as_view(),
        name="service_delete",
    ),
]
