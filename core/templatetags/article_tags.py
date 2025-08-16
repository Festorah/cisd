import re
from urllib.parse import urlencode

from django import template
from django.urls import reverse
from django.utils.html import strip_tags
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def reading_time(content):
    """Calculate estimated reading time for content"""
    if not content:
        return 0

    # Strip HTML tags and count words
    text = strip_tags(content)
    word_count = len(text.split())

    # Assume 200 words per minute reading speed
    minutes = max(1, word_count // 200)
    return minutes


@register.filter
def truncate_smart(text, length=100):
    """Smart truncation that respects word boundaries"""
    if len(text) <= length:
        return text

    truncated = text[:length]
    # Find the last space to avoid cutting words
    last_space = truncated.rfind(" ")
    if last_space > length * 0.8:  # Only if we're not cutting too much
        truncated = truncated[:last_space]

    return truncated + "..."


@register.simple_tag
def query_string(request, **kwargs):
    """Build query string preserving existing parameters"""
    query_dict = request.GET.copy()

    for key, value in kwargs.items():
        if value:
            query_dict[key] = value
        elif key in query_dict:
            del query_dict[key]

    return "?" + query_dict.urlencode() if query_dict else ""


@register.simple_tag
def active_if(request, url_name, **kwargs):
    """Return 'active' class if current URL matches the given URL name"""
    try:
        url = reverse(url_name, kwargs=kwargs)
        if request.path == url:
            return "active"
    except:
        pass
    return ""


@register.filter
def get_item(dictionary, key):
    """Get item from dictionary in template"""
    return dictionary.get(key)


@register.inclusion_tag("core/components/pagination.html", takes_context=True)
def render_pagination(context, page_obj, **kwargs):
    """Render pagination component with proper query parameters"""
    request = context["request"]

    # Preserve existing query parameters
    query_params = request.GET.copy()
    if "page" in query_params:
        del query_params["page"]

    base_url = request.path
    if query_params:
        base_url += "?" + query_params.urlencode() + "&"
    else:
        base_url += "?"

    return {
        "page_obj": page_obj,
        "base_url": base_url,
        "request": request,
    }


@register.inclusion_tag("core/components/article_card.html")
def render_article_card(article, show_excerpt=True, show_stats=True):
    """Render article card component"""
    return {
        "article": article,
        "show_excerpt": show_excerpt,
        "show_stats": show_stats,
    }


@register.filter
def highlight_search(text, search_query):
    """Highlight search terms in text"""
    if not search_query or not text:
        return text

    # Escape HTML in search query
    search_query = template.html.escape(search_query)

    # Create pattern for case-insensitive search
    pattern = re.compile(re.escape(search_query), re.IGNORECASE)

    # Replace with highlighted version
    highlighted = pattern.sub(
        f'<mark class="search-highlight">{search_query}</mark>', text
    )

    return mark_safe(highlighted)


@register.simple_tag
def category_color(category_name):
    """Get the color for a category"""
    color_map = {
        "analysis": "#dc2626",
        "campaign": "#059669",
        "explainer": "#2563eb",
        "qna": "#7c3aed",
        "news": "#ea580c",
        "research": "#0891b2",
        "opinion": "#be185d",
    }
    return color_map.get(category_name, "#6b7280")


@register.filter
def format_number(value):
    """Format numbers with K, M suffixes"""
    try:
        value = int(value)
        if value >= 1000000:
            return f"{value / 1000000:.1f}M"
        elif value >= 1000:
            return f"{value / 1000:.1f}K"
        else:
            return str(value)
    except (ValueError, TypeError):
        return value


@register.simple_tag
def get_url_params(request, **kwargs):
    """Get URL with updated parameters"""
    query_dict = request.GET.copy()

    for key, value in kwargs.items():
        if value:
            query_dict[key] = value
        elif key in query_dict:
            del query_dict[key]

    return query_dict.urlencode()


@register.filter
def time_since_short(value):
    """Short time since format (e.g., '2h ago', '3d ago')"""
    from datetime import timedelta

    from django.utils import timezone

    if not value:
        return ""

    now = timezone.now()
    diff = now - value

    if diff < timedelta(hours=1):
        return f"{diff.seconds // 60}m ago"
    elif diff < timedelta(days=1):
        return f"{diff.seconds // 3600}h ago"
    elif diff < timedelta(days=7):
        return f"{diff.days}d ago"
    elif diff < timedelta(days=30):
        return f"{diff.days // 7}w ago"
    else:
        return value.strftime("%b %d, %Y")


@register.inclusion_tag("core/components/social_share.html")
def social_share_buttons(article, request):
    """Render social media share buttons"""
    if hasattr(request, "build_absolute_uri"):
        article_url = request.build_absolute_uri(article.get_absolute_url())
    else:
        article_url = article.get_absolute_url()

    return {
        "article": article,
        "article_url": article_url,
        "twitter_text": f"{article.title} - {article.excerpt[:100]}...",
    }


@register.simple_tag
def breadcrumb_item(title, url=None, active=False):
    """Generate breadcrumb item"""
    if active:
        return mark_safe(
            f'<li class="breadcrumb-item active" aria-current="page">{title}</li>'
        )
    elif url:
        return mark_safe(
            f'<li class="breadcrumb-item"><a href="{url}">{title}</a></li>'
        )
    else:
        return mark_safe(f'<li class="breadcrumb-item">{title}</li>')


@register.filter
def dict_get(dictionary, key):
    """Get value from dictionary by key"""
    if isinstance(dictionary, dict):
        return dictionary.get(key, "")
    return ""


@register.simple_tag
def field_value(form, field_name):
    """Get the value of a form field"""
    if hasattr(form, "cleaned_data") and field_name in form.cleaned_data:
        return form.cleaned_data[field_name]
    elif hasattr(form, "data") and field_name in form.data:
        return form.data[field_name]
    elif hasattr(form, "initial") and field_name in form.initial:
        return form.initial[field_name]
    return ""
