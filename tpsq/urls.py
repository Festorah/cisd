from django.urls import path

from . import views

urlpatterns = [
    # API Endpoints
    path("api/early-access/", views.submit_early_access, name="submit_early_access"),
    path("api/track-event/", views.track_event, name="track_event"),
    path("api/dashboard-stats/", views.dashboard_stats, name="dashboard_stats"),
    path("api/check-email/", views.check_email_exists, name="check_email_exists"),
    path("api/stats/", views.stats_summary, name="stats_summary"),
    # Frontend Pages
    path("", views.LandingPageView.as_view(), name="landing_page"),
    path("api/csrf-token/", views.csrf_token, name="csrf_token"),
    path("intervention/", views.LandingPageView.as_view(), name="intervention"),
    path("speakup/", views.LandingPageView.as_view(), name="speakup"),
    path("accountability/", views.LandingPageView.as_view(), name="accountability"),
    # Dashboard
    path("tpsq/dashboard/", views.DashboardView.as_view(), name="dashboard"),
    path("tpsq/analytics/", views.DashboardView.as_view(), name="analytics"),
]
