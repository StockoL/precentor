from django.urls import path

from . import views

app_name = "members"
urlpatterns = [
    path("", views.MemberListView.as_view(), name="member_list"),
    path("<int:pk>/role/", views.change_role, name="change_role"),
    path("<int:pk>/remove/", views.MemberRemoveView.as_view(), name="remove"),
    path("<int:pk>/restore/", views.restore_member, name="restore"),
    path("invite/", views.InvitationCreateView.as_view(), name="invite"),
    path("invitations/<int:pk>/", views.InvitationLinkView.as_view(), name="invitation_link"),
    path("invitations/<int:pk>/cancel/", views.InvitationCancelView.as_view(), name="invitation_cancel"),
]
