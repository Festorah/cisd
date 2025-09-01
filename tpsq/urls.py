from django.urls import path
from tpsq import views

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
    path("report/", views.ReportView.as_view(), name="report"),
    path("speakup/", views.LandingPageView.as_view(), name="speakup"),
    path("accountability/", views.LandingPageView.as_view(), name="accountability"),
    # Dashboard
    path("tpsq/dashboard/", views.DashboardView.as_view(), name="dashboard"),
    path("tpsq/analytics/", views.DashboardView.as_view(), name="analytics"),
    path(
        "tpsq/dashboard/reports/",
        views.ReportDashboardView.as_view(),
        name="reports-dashboard",
    ),
    # Pretotype API Endpoints
    path("api/pretotype-track/", views.pretotype_track_event, name="pretotype_track"),
    path("api/pretotype-issue/", views.pretotype_submit_issue, name="pretotype_issue"),
    path(
        "api/pretotype-contact/",
        views.pretotype_submit_contact,
        name="pretotype_contact",
    ),
    # Media Upload Endpoints
    path(
        "api/pretotype-upload-media/",  # NEW: Multi-media upload endpoint
        views.pretotype_upload_media,
        name="pretotype_upload_media",
    ),
    path(
        "api/pretotype-upload-image/",  # DEPRECATED: Kept for backward compatibility
        views.pretotype_upload_image,
        name="pretotype_upload_image",
    ),
    # Analytics
    path(
        "api/pretotype-analytics/",
        views.pretotype_analytics_dashboard,
        name="pretotype_analytics",
    ),
    # Pretotype Social Feed
    path("community/", views.PretotypeFeedView.as_view(), name="pretotype_feed"),
    # Feed API Endpoints
    path("api/pretotype-comment/", views.add_comment, name="add_comment"),
    path("api/pretotype-reaction/", views.add_reaction, name="add_reaction"),
    path(
        "api/pretotype-comments/<uuid:issue_id>/",
        views.get_issue_comments,
        name="get_issue_comments",
    ),
    path(
        "api/pretotype-comment-upvote/",
        views.upvote_comment,
        name="upvote_comment",
    ),
]
