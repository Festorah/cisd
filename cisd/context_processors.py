from core.models import Category, SiteSettings, Tag
from django.conf import settings


def site_context(request):
    """Enhanced context processor for site-wide data"""
    try:
        site_settings = SiteSettings.get_settings()
    except:
        site_settings = None

    # Get popular categories
    popular_categories = Category.objects.filter(is_active=True).order_by("sort_order")[
        :6
    ]

    # Get featured tags
    featured_tags = Tag.objects.filter(is_featured=True).order_by("-usage_count")[:8]

    # Check if user is admin
    is_admin = False
    if request.user.is_authenticated:
        is_admin = request.user.is_staff or request.user.is_superuser

    return {
        "site_settings": site_settings,
        "popular_categories": popular_categories,
        "featured_tags": featured_tags,
        "is_admin": is_admin,
        "cms_version": "1.0.0",
        "debug_mode": getattr(settings, "DEBUG", False),
    }
