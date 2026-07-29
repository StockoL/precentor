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
    path(
        "terms/<int:term_pk>/music-list/", views.term_music_list, name="term_music_list"
    ),
    path(
        "terms/<int:term_pk>/markers/add/",
        views.TermMarkerCreateView.as_view(),
        name="marker_create",
    ),
    path(
        "markers/<int:pk>/edit/",
        views.TermMarkerUpdateView.as_view(),
        name="marker_update",
    ),
    path(
        "markers/<int:pk>/delete/",
        views.TermMarkerDeleteView.as_view(),
        name="marker_delete",
    ),
    path(
        "services/<int:service_pk>/roles/add/", views.add_role, name="add_role"
    ),
    path("roles/<int:role_pk>/pieces/add/", views.add_piece, name="add_piece"),
    path(
        "pieces/<int:piece_pk>/toggle-confirm/",
        views.toggle_confirm,
        name="toggle_confirm",
    ),
]
