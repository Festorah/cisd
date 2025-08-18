from core.models import Article, Author, Category, CloudinaryMedia, Event, Subscriber
from django.db import models
from django.db.models import Count, F, Q, Sum
from django.utils import timezone


class DashboardStatsManager:
    """Manager for dashboard statistics and analytics"""

    @staticmethod
    def get_overview_stats():
        """Get main dashboard statistics"""
        now = timezone.now()
        thirty_days_ago = now - timezone.timedelta(days=30)

        stats = {
            "articles": {
                "total": Article.objects.count(),
                "published": Article.objects.filter(status="published").count(),
                "draft": Article.objects.filter(status="draft").count(),
                "review": Article.objects.filter(status="review").count(),
                "scheduled": Article.objects.filter(status="scheduled").count(),
                "this_month": Article.objects.filter(
                    created_at__gte=thirty_days_ago
                ).count(),
            },
            "content": {
                "total_views": Article.objects.aggregate(total=Sum("view_count"))[
                    "total"
                ]
                or 0,
                "avg_reading_time": Article.objects.filter(
                    status="published"
                ).aggregate(avg=models.Avg("content_sections__order"))["avg"]
                or 0,
                "featured_count": Article.objects.filter(
                    is_featured=True, status="published"
                ).count(),
            },
            "users": {
                "total_subscribers": Subscriber.objects.filter(is_active=True).count(),
                "new_subscribers": Subscriber.objects.filter(
                    created_at__gte=thirty_days_ago
                ).count(),
                "confirmed_subscribers": Subscriber.objects.filter(
                    is_active=True, confirmed_at__isnull=False
                ).count(),
            },
            "media": {
                "total_files": CloudinaryMedia.objects.count(),
                "total_size": CloudinaryMedia.objects.aggregate(total=Sum("file_size"))[
                    "total"
                ]
                or 0,
                "images": CloudinaryMedia.objects.filter(file_type="image").count(),
                "videos": CloudinaryMedia.objects.filter(file_type="video").count(),
            },
            "events": {
                "upcoming": Event.objects.filter(
                    start_datetime__gt=now, status="upcoming"
                ).count(),
                "this_month": Event.objects.filter(
                    start_datetime__month=now.month, start_datetime__year=now.year
                ).count(),
            },
        }

        return stats

    @staticmethod
    def get_recent_activity(limit=10):
        """Get recent activity across the platform"""
        recent_articles = Article.objects.select_related(
            "author", "category", "created_by"
        ).order_by("-updated_at")[:limit]

        return {
            "recent_articles": recent_articles,
            "recent_media": CloudinaryMedia.objects.select_related(
                "uploaded_by"
            ).order_by("-created_at")[:5],
        }

    @staticmethod
    def get_popular_content():
        """Get popular and trending content"""
        return {
            "most_viewed": Article.objects.filter(status="published").order_by(
                "-view_count"
            )[:5],
            "most_shared": Article.objects.filter(status="published").order_by(
                "-share_count"
            )[:5],
            "trending_tags": Category.objects.annotate(
                article_count=Count("articles", filter=Q(articles__status="published"))
            ).order_by("-article_count")[:5],
        }


class ArticleManager:
    """Enhanced manager for article operations"""

    @staticmethod
    def get_optimized_articles_list(filters=None):
        """Get optimized articles list with proper relations"""
        queryset = (
            Article.objects.select_related(
                "category", "author", "featured_image", "created_by", "last_modified_by"
            )
            .prefetch_related("tags", "content_sections")
            .order_by("-updated_at")
        )

        if filters:
            if filters.get("status"):
                queryset = queryset.filter(status=filters["status"])
            if filters.get("category"):
                queryset = queryset.filter(category_id=filters["category"])
            if filters.get("author"):
                queryset = queryset.filter(author_id=filters["author"])
            if filters.get("search"):
                queryset = queryset.filter(
                    Q(title__icontains=filters["search"])
                    | Q(excerpt__icontains=filters["search"])
                )

        return queryset

    @staticmethod
    def create_article_with_sections(article_data, sections_data, user):
        """Create article with content sections in a transaction"""
        from django.db import transaction

        with transaction.atomic():
            # Create article
            article = Article.objects.create(
                title=article_data["title"],
                excerpt=article_data["excerpt"],
                category_id=article_data["category_id"],
                author_id=article_data["author_id"],
                featured_image_id=article_data.get("featured_image_id"),
                status=article_data.get("status", "draft"),
                created_by=user,
                last_modified_by=user,
                meta_title=article_data.get("meta_title", ""),
                meta_description=article_data.get("meta_description", ""),
            )

            # Add tags
            if article_data.get("tag_ids"):
                article.tags.set(article_data["tag_ids"])

            # Create content sections
            from core.models import ContentSection

            for order, section_data in enumerate(sections_data):
                ContentSection.objects.create(
                    article=article,
                    section_type=section_data["type"],
                    order=order,
                    content=section_data.get("content", ""),
                    title=section_data.get("title", ""),
                    media_file_id=section_data.get("media_file_id"),
                    caption=section_data.get("caption", ""),
                    alt_text=section_data.get("alt_text", ""),
                    question=section_data.get("question", ""),
                    answer=section_data.get("answer", ""),
                    interviewer=section_data.get("interviewer", ""),
                    interviewee=section_data.get("interviewee", ""),
                )

            return article
