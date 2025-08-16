import hashlib

from django.conf import settings

# utils/cache_utils.py
from django.core.cache import cache


class CacheManager:
    """Helper class for managing cache operations."""

    # Cache timeouts (in seconds)
    ARTICLE_CACHE_TIMEOUT = 3600  # 1 hour
    MEDIA_CACHE_TIMEOUT = 86400  # 24 hours
    SETTINGS_CACHE_TIMEOUT = 3600  # 1 hour
    STATS_CACHE_TIMEOUT = 900  # 15 minutes

    @classmethod
    def get_article_cache_key(cls, slug):
        """Generate cache key for article detail."""
        return f"article:detail:{slug}"

    @classmethod
    def get_media_cache_key(cls, public_id):
        """Generate cache key for media info."""
        return f"media:info:{public_id}"

    @classmethod
    def get_stats_cache_key(cls, stats_type):
        """Generate cache key for statistics."""
        return f"stats:{stats_type}"

    @classmethod
    def cache_article(cls, article):
        """Cache article data."""
        cache_key = cls.get_article_cache_key(article.slug)
        cache.set(cache_key, article, cls.ARTICLE_CACHE_TIMEOUT)

    @classmethod
    def get_cached_article(cls, slug):
        """Get cached article data."""
        cache_key = cls.get_article_cache_key(slug)
        return cache.get(cache_key)

    @classmethod
    def invalidate_article_cache(cls, slug):
        """Invalidate article cache."""
        cache_key = cls.get_article_cache_key(slug)
        cache.delete(cache_key)

    @classmethod
    def cache_media_info(cls, public_id, info):
        """Cache media file information."""
        cache_key = cls.get_media_cache_key(public_id)
        cache.set(cache_key, info, cls.MEDIA_CACHE_TIMEOUT)

    @classmethod
    def get_cached_media_info(cls, public_id):
        """Get cached media information."""
        cache_key = cls.get_media_cache_key(public_id)
        return cache.get(cache_key)
