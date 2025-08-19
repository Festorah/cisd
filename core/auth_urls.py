from django.contrib.auth import views as auth_views
from django.urls import path

from . import auth_views as custom_auth_views

app_name = "auth"

urlpatterns = [
    # Login and Logout
    path("login/", custom_auth_views.CustomLoginView.as_view(), name="login"),
    path("logout/", custom_auth_views.CustomLogoutView.as_view(), name="logout"),
    # Password Reset Flow
    path(
        "password-reset/",
        custom_auth_views.CustomPasswordResetView.as_view(),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        custom_auth_views.CustomPasswordResetDoneView.as_view(),
        name="password_reset_done",
    ),
    path(
        "password-reset/confirm/<uidb64>/<token>/",
        custom_auth_views.CustomPasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "password-reset/complete/",
        custom_auth_views.CustomPasswordResetCompleteView.as_view(),
        name="password_reset_complete",
    ),
    # Profile
    path("profile/", custom_auth_views.profile_view, name="profile"),
]

# Alternative URL patterns for compatibility with Django's default auth URLs
# You can also use these in your main urls.py if you prefer

# auth_urlpatterns = [
#     # Main authentication URLs
#     path("accounts/login/", custom_auth_views.CustomLoginView.as_view(), name="login"),
#     path(
#         "accounts/logout/", custom_auth_views.CustomLogoutView.as_view(), name="logout"
#     ),
#     # Password reset URLs (matches Django's default pattern)
#     path(
#         "accounts/password_reset/",
#         custom_auth_views.CustomPasswordResetView.as_view(),
#         name="password_reset",
#     ),
#     path(
#         "accounts/password_reset/done/",
#         custom_auth_views.CustomPasswordResetDoneView.as_view(),
#         name="password_reset_done",
#     ),
#     path(
#         "accounts/reset/<uidb64>/<token>/",
#         custom_auth_views.CustomPasswordResetConfirmView.as_view(),
#         name="password_reset_confirm",
#     ),
#     path(
#         "accounts/reset/done/",
#         custom_auth_views.CustomPasswordResetCompleteView.as_view(),
#         name="password_reset_complete",
#     ),
#     # Profile
#     path("accounts/profile/", custom_auth_views.profile_view, name="profile"),
# ]
