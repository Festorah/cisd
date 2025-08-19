import html
import re

from django.db import models

# utils/model_utils.py
from django.utils.text import slugify


def generate_unique_slug(model_class, title, instance=None):
    """
    Generate a unique slug for any model with a slug field.

    Args:
        model_class: Django model class
        title: Text to generate slug from
        instance: Existing instance (for updates)

    Returns:
        str: Unique slug
    """
    base_slug = slugify(title)
    if not base_slug:
        base_slug = "untitled"

    slug = base_slug
    counter = 1

    while True:
        queryset = model_class.objects.filter(slug=slug)
        if instance and instance.pk:
            queryset = queryset.exclude(pk=instance.pk)

        if not queryset.exists():
            break

        slug = f"{base_slug}-{counter}"
        counter += 1

    return slug


def extract_text_from_html(html_content):
    """
    Extract plain text from HTML content for reading time calculation.

    Args:
        html_content: HTML string

    Returns:
        str: Plain text content
    """
    if not html_content:
        return ""

    # Remove HTML tags
    text = re.sub(r"<[^<]+?>", "", html_content)
    # Decode HTML entities
    text = html.unescape(text)
    # Remove extra whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text


def calculate_reading_time(content_sections, wpm=200):
    """
    Calculate estimated reading time for article content.

    Args:
        content_sections: QuerySet or list of ContentSection objects
        wpm: Words per minute reading speed

    Returns:
        int: Reading time in minutes
    """
    total_words = 0

    for section in content_sections:
        # Count words in main content
        if hasattr(section, "content") and section.content:
            text = extract_text_from_html(section.content)
            total_words += len(text.split())

        # Count words in title
        if hasattr(section, "title") and section.title:
            total_words += len(section.title.split())

        # Count words in interview sections
        if hasattr(section, "question") and section.question:
            total_words += len(section.question.split())
        if hasattr(section, "answer") and section.answer:
            total_words += len(section.answer.split())

        # Count words in captions
        if hasattr(section, "caption") and section.caption:
            total_words += len(section.caption.split())

    # Calculate reading time (minimum 1 minute)
    return max(1, total_words // wpm)


def optimize_database_queries():
    """
    Utility function to provide optimized querysets for common operations.
    """
    from core.models import Article, CloudinaryMedia, ContentSection

    class OptimizedQueries:
        @staticmethod
        def get_published_articles():
            """Get published articles with related data optimized."""
            return (
                Article.objects.filter(status="published")
                .select_related("category", "author", "featured_image")
                .prefetch_related("tags", "content_sections__media_file")
                .order_by("-published_date")
            )

        @staticmethod
        def get_article_detail(slug):
            """Get article detail with all related data."""
            return (
                Article.objects.filter(slug=slug, status="published")
                .select_related(
                    "category",
                    "author",
                    "featured_image",
                    "created_by",
                    "last_modified_by",
                )
                .prefetch_related(
                    "tags",
                    "content_sections__media_file",
                )
                .first()
            )

        @staticmethod
        def get_article_content_sections(article):
            """Get optimized content sections for an article."""
            return (
                ContentSection.objects.filter(article=article)
                .select_related("media_file")
                .order_by("order")
            )

        @staticmethod
        def get_featured_articles(limit=3):
            """Get featured articles for homepage hero carousel."""
            return (
                Article.objects.filter(status="published", is_featured=True)
                .select_related("category", "author", "featured_image")
                .prefetch_related("tags")
                .order_by("-published_date")[:limit]
            )

        @staticmethod
        def get_featured_updates(exclude_ids=None, limit=3):
            """
            Get featured articles for the Featured Updates section.
            Excludes articles already shown in hero section.
            Falls back to latest articles if not enough featured ones.

            Args:
                exclude_ids: List of article IDs to exclude (usually from hero section)
                limit: Number of articles to return

            Returns:
                QuerySet: Articles for featured updates section
            """
            if exclude_ids is None:
                exclude_ids = []

            # First try to get featured articles not already used
            featured_updates = (
                Article.objects.filter(status="published", is_featured=True)
                .exclude(id__in=exclude_ids)
                .select_related("category", "author", "featured_image")
                .prefetch_related("tags")
                .order_by("-published_date")[:limit]
            )

            # If we don't have enough featured articles, fill with latest published articles
            featured_count = featured_updates.count()
            if featured_count < limit:
                # Get IDs of articles we already have
                used_ids = list(exclude_ids) + list(
                    featured_updates.values_list("id", flat=True)
                )

                # Get additional latest articles to fill the gap
                additional_articles = (
                    Article.objects.filter(status="published")
                    .exclude(id__in=used_ids)
                    .select_related("category", "author", "featured_image")
                    .prefetch_related("tags")
                    .order_by("-published_date")[: (limit - featured_count)]
                )

                # Combine the querysets
                return list(featured_updates) + list(additional_articles)

            return featured_updates

        @staticmethod
        def get_popular_articles(limit=5):
            """Get most viewed articles."""
            return (
                Article.objects.filter(status="published")
                .select_related("category", "author", "featured_image")
                .order_by("-view_count", "-published_date")[:limit]
            )

        @staticmethod
        def get_recent_media(limit=20):
            """Get recently uploaded media files."""
            return CloudinaryMedia.objects.select_related("uploaded_by").order_by(
                "-created_at"
            )[:limit]

    return OptimizedQueries
