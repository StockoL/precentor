from django.urls import path

from . import views

app_name = "library"

urlpatterns = [
    path("", views.ScoreListView.as_view(), name="score_list"),
    path("<int:pk>/", views.ScoreDetailView.as_view(), name="score_detail"),
    path("add/", views.ScoreCreateView.as_view(), name="score_create"),
    path("<int:pk>/edit/", views.ScoreUpdateView.as_view(), name="score_update"),
    path("<int:pk>/delete/", views.ScoreDeleteView.as_view(), name="score_delete"),
    path("import/", views.ScoreImportView.as_view(), name="score_import"),
    path("imports/", views.ScoreImportListView.as_view(), name="score_import_list"),
    path("import/template/", views.import_template, name="import_template"),
    path("export/", views.export_library, name="export_library"),
    path("completeness/", views.completeness, name="completeness"),
    path("hymnals/", views.HymnalListView.as_view(), name="hymnal_list"),
    path("hymnals/add/", views.HymnalCreateView.as_view(), name="hymnal_create"),
    path("hymnals/<int:pk>/", views.HymnalDetailView.as_view(), name="hymnal_detail"),
    path("hymns/<int:pk>/", views.HymnDetailView.as_view(), name="hymn_detail"),
    path("hymns/<int:pk>/edit/", views.HymnUpdateView.as_view(), name="hymn_update"),
    path("hymnals/<int:pk>/edit/", views.HymnalUpdateView.as_view(), name="hymnal_update"),
    path("hymnals/<int:pk>/delete/", views.HymnalDeleteView.as_view(), name="hymnal_delete"),
    path("import/<int:pk>/", views.ScoreImportDetailView.as_view(), name="score_import_detail"),
    path("import/<int:pk>/keep/", views.keep_import, name="keep_import"),
    path("import/<int:pk>/remove/", views.remove_import, name="remove_import"),
]
