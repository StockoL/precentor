from django.urls import path

from . import views

app_name = "members"
urlpatterns = [
    path("invite/", views.InvitationCreateView.as_view(), name="invite"),
    path("invitations/<int:pk>/", views.InvitationLinkView.as_view(), name="invitation_link"),
]
