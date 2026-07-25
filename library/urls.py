from django.urls import path

from . import views

app_name = "library"

urlpatterns = [
    path("", views.ScoreListView.as_view(), name="score_list"),
    path("<int:pk>/", views.ScoreDetailView.as_view(), name="score_detail"),
    path("add/", views.ScoreCreateView.as_view(), name="score_create"),
    path("<int:pk>/edit/", views.ScoreUpdateView.as_view(), name="score_update"),
    path("<int:pk>/delete/", views.ScoreDeleteView.as_view(), name="score_delete"),
]
