from datetime import timedelta

from django.db import models
from django.db.models import Avg, Count, Sum
from django.utils import timezone


class AnalyticsManager:
    """Manager for analytics and reporting"""

    @staticmethod
    def get_content_stats(days=30):
        """Get content statistics for the specified period"""
        from core.models import Article, CloudinaryMedia, Newsletter

        since_date = timezone.now() - timedelta(days=days)

        return {
            "articles_published": Article.objects.filter(
                published_date__gte=since_date, status="published"
            ).count(),
            "total_views": Article.objects.aggregate(total=Sum("view_count"))["total"]
            or 0,
            "average_reading_time": Article.objects.filter(
                status="published"
            ).aggregate(avg=Avg("content_sections__order"))["avg"]
            or 0,
            "media_uploaded": CloudinaryMedia.objects.filter(
                created_at__gte=since_date
            ).count(),
            "newsletters_sent": Newsletter.objects.filter(
                sent_date__gte=since_date, is_sent=True
            ).count(),
        }

    @staticmethod
    def get_popular_content(limit=10):
        """Get most popular content by views"""
        from core.models import Article

        return (
            Article.objects.filter(status="published")
            .select_related("category", "author")
            .order_by("-view_count")[:limit]
        )

    @staticmethod
    def get_author_performance():
        """Get author performance statistics"""
        from core.models import Article, Author

        return (
            Author.objects.annotate(
                article_count=Count(
                    "articles", filter=models.Q(articles__status="published")
                ),
                total_views=Sum("articles__view_count"),
                avg_views=Avg("articles__view_count"),
            )
            .filter(article_count__gt=0)
            .order_by("-total_views")
        )

    @staticmethod
    def get_category_distribution():
        """Get content distribution by category"""
        from core.models import Category

        return (
            Category.objects.annotate(
                article_count=Count(
                    "articles", filter=models.Q(articles__status="published")
                ),
                total_views=Sum("articles__view_count"),
            )
            .filter(article_count__gt=0)
            .order_by("-article_count")
        )
