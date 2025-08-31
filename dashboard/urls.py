from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    # Dashboard home
    path("", views.DashboardHomeView.as_view(), name="home"),
    # Article management
    path("article/create/", views.ArticleCreateView.as_view(), name="article_create"),
    path("articles/", views.articles_list_view, name="articles_list"),
    path(
        "article/<uuid:article_id>/edit/",
        views.article_edit_view,
        name="article_edit",
    ),
    # Media management
    path("media/", views.media_library_view, name="media_library"),
    # AJAX endpoints for the new article create functionality
    path("ajax/save-article/", views.save_article_view, name="save_article"),
    path("ajax/upload-file/", views.upload_file_view, name="upload_file"),
    path(
        "ajax/delete-media/<uuid:media_id>/",
        views.delete_media_view,
        name="delete_media",
    ),
    path("ajax/stats/", views.dashboard_stats_view, name="dashboard_stats"),
    path("ajax/bulk-articles/", views.bulk_articles_view, name="bulk_articles"),
    path(
        "ajax/delete-article/<uuid:article_id>/",
        views.delete_article_view,
        name="delete_article",
    ),
    path(
        "ajax/toggle-featured/<uuid:article_id>/",
        views.toggle_featured_view,
        name="toggle_featured",
    ),
    path(
        "ajax/duplicate-article/<uuid:article_id>/",
        views.duplicate_article_view,
        name="duplicate_article",
    ),
    path("ajax/create-category/", views.create_category_view, name="create_category"),
    path("ajax/create-author/", views.create_author_view, name="create_author"),
]
