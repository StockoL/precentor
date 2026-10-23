"""
URL configuration for precentor_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from accounts.forms import EmailAuthenticationForm, NewPasswordForm
from accounts.views import JoinView, SignUpView

urlpatterns = [
    path("admin/", admin.site.urls),
    # Ahead of Django's own auth URLs, so the login page asks for an email.
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(authentication_form=EmailAuthenticationForm),
        name="login",
    ),
    path("accounts/signup/", SignUpView.as_view(), name="signup"),
    path("join/<str:token>/", JoinView.as_view(), name="join"),
    # Django's own account pages, listed one by one rather than included
    # whole: its "email me a reset link" pages are left out, as Precentor
    # sends no email. The owner makes reset links instead (accounts).
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("accounts/password_change/", auth_views.PasswordChangeView.as_view(), name="password_change"),
    path(
        "accounts/password_change/done/",
        auth_views.PasswordChangeDoneView.as_view(),
        name="password_change_done",
    ),
    path(
        "accounts/reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(form_class=NewPasswordForm),
        name="password_reset_confirm",
    ),
    path("accounts/reset/done/", auth_views.PasswordResetCompleteView.as_view(), name="password_reset_complete"),
    path("members/", include("accounts.urls")),
    path("library/", include("library.urls")),
    path("ordo/", include("ordo.urls")),
    path("settings/", include("core.urls")),
    path("", include("planning.urls")),
    path("comments/", include("comments.urls")),
]
