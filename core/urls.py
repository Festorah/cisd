from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

# API Router
router = DefaultRouter()
router.register(r"articles", views.ArticleViewSet, basename="article")
router.register(
    r"content-sections", views.ContentSectionViewSet, basename="contentsection"
)
router.register(r"media", views.CloudinaryMediaViewSet, basename="cloudinarymedia")
router.register(r"events", views.EventViewSet, basename="event")

# URL Patterns
urlpatterns = [
    # Public frontend URLs
    path("", views.HomePageView.as_view(), name="home"),
    path("articles/", views.ArticleListView.as_view(), name="articles"),
    path(
        "article/preview/", views.ArticlePreviewView.as_view(), name="article_preview"
    ),
    path(
        "article/<slug:slug>/", views.ArticleDetailView.as_view(), name="article_detail"
    ),
    path("events/", views.EventListView.as_view(), name="events"),
    # Admin dashboard URLs
    path(
        "admin/dashboard/", views.AdminDashboardView.as_view(), name="admin_dashboard"
    ),
    path(
        "admin/article/create/", views.article_create_view, name="admin_article_create"
    ),
    path(
        "admin/article/<uuid:article_id>/edit/",
        views.article_edit_view,
        name="admin_article_edit",
    ),
    # API URLs
    path("api/", include(router.urls)),
    path("api/save-article/", views.save_article_content, name="api_save_article"),
    path("api/bulk-actions/", views.bulk_article_action, name="api_bulk_actions"),
    path("api/stats/", views.get_dashboard_stats, name="api_stats"),
    # Enhanced inline editing endpoints
    path(
        "api/update-article-field/",
        views.update_article_field,
        name="api_update_article_field",
    ),
    path(
        "api/update-content-section/",
        views.update_content_section,
        name="api_update_content_section",
    ),
    path(
        "api/add-content-section/",
        views.add_content_section,
        name="api_add_content_section",
    ),
    path(
        "api/delete-content-section/<uuid:section_id>/",
        views.delete_content_section,
        name="api_delete_content_section",
    ),
    # Legacy endpoints (keep for compatibility)
    path("api/update-field/", views.update_article_field, name="api_update_field"),
    path(
        "api/article/<uuid:article_id>/delete/",
        views.delete_article,
        name="api_delete_article",
    ),
    # Newsletter subscription
    path("api/subscribe/", views.subscribe_newsletter, name="api_subscribe"),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
