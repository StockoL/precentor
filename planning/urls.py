from django.urls import path

from . import views

app_name = "planning"

urlpatterns = [
    path("", views.TermListView.as_view(), name="term_list"),
    path("terms/add/", views.TermCreateView.as_view(), name="term_create"),
    path("terms/<int:pk>/edit/", views.TermUpdateView.as_view(), name="term_update"),
    path("terms/<int:pk>/delete/", views.TermDeleteView.as_view(), name="term_delete"),
    path("terms/<int:pk>/", views.TermDetailView.as_view(), name="term_detail"),
]
