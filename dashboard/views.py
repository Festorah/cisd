import json
import logging
from functools import wraps

from core.forms import ArticleForm, ContentSectionFormSet
from core.models import (
    Article,
    Author,
    Category,
    CloudinaryMedia,
    ContentSection,
    Event,
    Newsletter,
    Subscriber,
    Tag,
)
from core.serializers import MediaUploadSerializer
from core.utils.cloudinary_utils import CloudinaryManager
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.generic import (
    CreateView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
)

# Import dashboard utilities
from .managers import ArticleManager, DashboardStatsManager
from .utils.file_processors import ContentGenerator, FileProcessor
from .utils.media_optimizer import MediaOptimizer

logger = logging.getLogger(__name__)


def is_admin_user(user):
    """Check if user has admin privileges"""
    return user.is_authenticated and (user.is_staff or user.is_superuser)


def admin_required(view_func=None, *, login_url="/auth/login/", message=None):
    """
    Enhanced decorator for admin-only views with custom login URL and messaging
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                # Add helpful message for unauthenticated users
                messages.info(
                    request, message or "Please sign in to access the admin dashboard."
                )
                return redirect(f"{login_url}?next={request.get_full_path()}")

            if not is_admin_user(request.user):
                # Add permission denied message for regular users
                messages.error(
                    request,
                    "You don't have permission to access this area. Contact an administrator if you need access.",
                )
                logger.warning(
                    f"User {request.user.username} attempted to access admin area at {request.get_full_path()}"
                )
                return redirect("home")  # Redirect to home instead of login

            return view_func(request, *args, **kwargs)

        return wrapper

    if view_func is None:
        return decorator
    else:
        return decorator(view_func)


def ajax_admin_required(view_func):
    """
    Decorator for AJAX views that require admin access
    Returns JSON responses instead of redirects
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(
                {
                    "success": False,
                    "error": "Authentication required",
                    "redirect": "/auth/login/",
                },
                status=401,
            )

        if not is_admin_user(request.user):
            logger.warning(
                f"User {request.user.username} attempted to access admin AJAX endpoint at {request.path}"
            )
            return JsonResponse(
                {"success": False, "error": "Administrator privileges required"},
                status=403,
            )

        return view_func(request, *args, **kwargs)

    return wrapper


class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Enhanced mixin to require admin access with custom auth integration
    """

    login_url = "/auth/login/"  # Use our custom login URL
    permission_denied_message = "Administrator privileges required to access this page."

    def test_func(self):
        return is_admin_user(self.request.user)

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            messages.info(self.request, "Please sign in to access the admin dashboard.")
            return redirect(
                f"{self.get_login_url()}?next={self.request.get_full_path()}"
            )
        else:
            # User is authenticated but not admin
            messages.error(self.request, self.permission_denied_message)
            logger.warning(
                f"User {self.request.user.username} attempted to access admin area at {self.request.get_full_path()}"
            )
            return redirect("home")


# Enhanced Dashboard Views with Custom Auth Integration


class DashboardHomeView(AdminRequiredMixin, ListView):
    """Dashboard homepage with real statistics - Protected"""

    template_name = "dashboard/home.html"
    context_object_name = "recent_articles"
    paginate_by = 10

    def get_queryset(self):
        return ArticleManager.get_optimized_articles_list()[:10]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get real dashboard statistics
        stats = DashboardStatsManager.get_overview_stats()
        recent_activity = DashboardStatsManager.get_recent_activity()
        popular_content = DashboardStatsManager.get_popular_content()

        context.update(
            {
                "stats": stats,
                "recent_activity": recent_activity,
                "popular_content": popular_content,
                "pending_reviews": Article.objects.filter(status="review")[:5],
                "scheduled_posts": Article.objects.filter(status="scheduled").order_by(
                    "scheduled_publish_date"
                )[:5],
                "user": self.request.user,  # Add user context for welcome message
            }
        )

        return context


@ajax_admin_required
@require_http_methods(["GET"])
def get_article_data(request, article_id):
    """Get article data for editing - Protected"""
    try:
        article = get_object_or_404(Article, id=article_id)

        # Get content sections
        content_sections = []
        for section in article.content_sections.all().order_by("order"):
            section_data = {
                "id": str(section.id),
                "type": section.section_type,
                "content": section.content or "",
                "title": section.title or "",
                "order": section.order,
                "media_file_id": (
                    str(section.media_file.id) if section.media_file else ""
                ),
                "caption": section.caption or "",
                "alt_text": section.alt_text or "",
                "question": section.question or "",
                "answer": section.answer or "",
            }
            content_sections.append(section_data)

        article_data = {
            "id": str(article.id),
            "title": article.title,
            "excerpt": article.excerpt,
            "category_id": str(article.category.id) if article.category else "",
            "author_id": str(article.author.id) if article.author else "",
            "featured_image_id": (
                str(article.featured_image.id) if article.featured_image else ""
            ),
            "status": article.status,
            "published_date": (
                article.published_date.isoformat() if article.published_date else ""
            ),
            "content_sections": content_sections,
            "meta_title": article.meta_title or "",
            "meta_description": article.meta_description or "",
            "meta_keywords": article.meta_keywords or "",
            "tags": [tag.name for tag in article.tags.all()],
            "is_featured": article.is_featured,
            "is_breaking": article.is_breaking,
            "allow_comments": article.allow_comments,
        }

        return JsonResponse({"success": True, "article": article_data})

    except Article.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "Article not found"}, status=404
        )
    except Exception as e:
        logger.error(f"Error getting article data: {str(e)}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


class ArticleCreateView(AdminRequiredMixin, TemplateView):
    """Create new article with enhanced functionality - Protected"""

    # template_name = "dashboard/enhanced_article_create.html"
    template_name = "dashboard/article_create.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get categories and authors for dropdowns
        categories = Category.objects.filter(is_active=True).order_by(
            "sort_order", "display_name"
        )
        authors = Author.objects.filter(is_active=True).order_by("name")

        # Get media files for the media library
        recent_media = CloudinaryMedia.objects.filter(file_type="image").order_by(
            "-created_at"
        )[:20]

        all_media = CloudinaryMedia.objects.order_by("-created_at")[:50]

        context.update(
            {
                "categories": categories,
                "authors": authors,
                "recent_media": recent_media,
                "all_media": all_media,
                "csrf_token": self.request.META.get("CSRF_COOKIE"),
            }
        )

        return context


# Protected Function-Based Views


@admin_required(message="Please sign in to access the article editor.")
def article_editor_view(request, article_id=None):
    """Enhanced article editor with real-time functionality - Protected"""
    article = None
    if article_id:
        article = get_object_or_404(Article, id=article_id)

    context = {
        "article": article,
        "categories": Category.objects.filter(is_active=True),
        "authors": Author.objects.filter(is_active=True),
        "tags": Tag.objects.all().order_by("name"),
        "recent_media": CloudinaryMedia.objects.order_by("-created_at")[:50],
        "default_structure": ContentGenerator.get_default_structure(),
    }

    return render(request, "dashboard/article_editor.html", context)


@admin_required(message="Please sign in to access the media library.")
def media_library_view(request):
    """Media library with pagination and search - Protected"""
    media_list = CloudinaryMedia.objects.select_related("uploaded_by").order_by(
        "-created_at"
    )

    # Apply filters
    file_type = request.GET.get("type")
    if file_type:
        media_list = media_list.filter(file_type=file_type)

    search = request.GET.get("search")
    if search:
        media_list = media_list.filter(title__icontains=search)

    paginator = Paginator(media_list, 24)  # 24 items per page
    page_number = request.GET.get("page")
    media_page = paginator.get_page(page_number)

    context = {
        "media_page": media_page,
        "file_types": CloudinaryMedia.objects.values_list(
            "file_type", flat=True
        ).distinct(),
        "current_filters": {
            "type": file_type,
            "search": search,
        },
    }

    return render(request, "dashboard/media_library.html", context)


@admin_required()
def articles_list_view(request):
    """Display all articles with filtering and pagination - Protected"""
    articles = Article.objects.select_related(
        "category", "author", "featured_image"
    ).order_by("-updated_at")

    # Apply filters
    search = request.GET.get("search")
    if search:
        articles = articles.filter(
            Q(title__icontains=search)
            | Q(excerpt__icontains=search)
            | Q(author__name__icontains=search)
        )

    status = request.GET.get("status")
    if status:
        articles = articles.filter(status=status)

    category = request.GET.get("category")
    if category:
        articles = articles.filter(category_id=category)

    author = request.GET.get("author")
    if author:
        articles = articles.filter(author_id=author)

    # Pagination
    paginator = Paginator(articles, 20)  # 20 articles per page
    page_number = request.GET.get("page")
    articles_page = paginator.get_page(page_number)

    # Get filter options
    categories = Category.objects.filter(is_active=True).order_by(
        "sort_order", "display_name"
    )
    authors = Author.objects.filter(is_active=True).order_by("name")

    context = {
        "articles": articles_page,
        "categories": categories,
        "authors": authors,
    }

    return render(request, "dashboard/articles_list.html", context)


# @admin_required()
# def article_edit_view(request, article_id):
#     """Edit an existing article with properly loaded content - Protected"""
#     article = get_object_or_404(Article, id=article_id)

#     # Get content sections ordered properly
#     content_sections = article.content_sections.all().order_by("order")

#     # Serialize content sections for JavaScript with proper handling of None values
#     sections_data = []
#     for section in content_sections:
#         section_data = {
#             "id": str(section.id) if section.id else "",
#             "type": section.section_type or "paragraph",
#             "content": section.content or "",
#             "title": section.title or "",
#             "order": section.order if section.order is not None else 0,
#             "media_file_id": str(section.media_file.id) if section.media_file else "",
#             "caption": section.caption or "",
#             "alt_text": section.alt_text or "",
#             "question": section.question or "",
#             "answer": section.answer or "",
#             "interviewer": section.interviewer or "",
#             "interviewee": section.interviewee or "",
#             "attribution": getattr(section, "attribution", "") or "",  # For quotes
#         }
#         sections_data.append(section_data)

#     # Get dropdown options
#     categories = Category.objects.filter(is_active=True).order_by(
#         "sort_order", "display_name"
#     )
#     authors = Author.objects.filter(is_active=True).order_by("name")
#     recent_media = CloudinaryMedia.objects.order_by("-created_at")[:50]

#     # Prepare article data for JavaScript with proper None handling
#     article_data = {
#         "id": str(article.id),
#         "title": article.title or "",
#         "excerpt": article.excerpt or "",
#         "category_id": str(article.category.id) if article.category else "",
#         "author_id": str(article.author.id) if article.author else "",
#         "featured_image_id": (
#             str(article.featured_image.id) if article.featured_image else ""
#         ),
#         "status": article.status or "draft",
#         "published_date": (
#             article.published_date.isoformat() if article.published_date else ""
#         ),
#         "content_sections": sections_data,
#         "meta_title": article.meta_title or "",
#         "meta_description": article.meta_description or "",
#         "social_title": article.social_title or "",
#         "social_description": article.social_description or "",
#         "is_featured": article.is_featured,
#         "is_breaking": article.is_breaking,
#         "allow_comments": article.allow_comments,
#     }

#     context = {
#         "article": article,
#         "article_data_json": json.dumps(article_data),  # Properly serialized data
#         "categories": categories,
#         "authors": authors,
#         "recent_media": recent_media,
#     }

#     return render(request, "dashboard/article_edit.html", context)


@admin_required(message="Please sign in to access the article editor.")
def article_edit_view(request, article_id):
    """Enhanced article editor view for editing existing articles - Protected"""
    article = get_object_or_404(Article, id=article_id)

    # Get content sections ordered properly
    content_sections = article.content_sections.all().order_by("order")

    # Get dropdown options
    categories = Category.objects.filter(is_active=True).order_by(
        "sort_order", "display_name"
    )
    authors = Author.objects.filter(is_active=True).order_by("name")
    recent_media = CloudinaryMedia.objects.order_by("-created_at")[:50]

    context = {
        "article": article,
        "content_sections": content_sections,
        "categories": categories,
        "authors": authors,
        "recent_media": recent_media,
        "is_edit_mode": True,
    }

    return render(request, "dashboard/article_edit.html", context)


# Add this function to your views.py file


@admin_required(message="Please sign in to access the user manual.")
def user_manual_view(request):
    """
    Display the comprehensive user manual for the dashboard.
    This view provides detailed documentation on all dashboard features.
    """
    # You can add any dynamic content here if needed
    # For example, version information, user-specific tips, etc.

    context = {
        "dashboard_version": "2.1.0",  # You can make this dynamic
        "last_updated": "2024-12-19",  # Update when you modify the manual
        "user_role": "Admin" if request.user.is_staff else "Editor",
        "quick_stats": {
            "total_features": 50,  # Update based on your actual feature count
            "keyboard_shortcuts": 15,
            "supported_file_types": 8,
        },
    }

    return render(request, "dashboard/user_manual.html", context)


# Protected AJAX Views


@csrf_exempt
@ajax_admin_required
@require_http_methods(["POST"])
def save_article_ajax(request):
    """Save article via AJAX with proper validation - Protected"""
    try:
        data = json.loads(request.body)

        # Validate required fields
        required_fields = ["title", "excerpt", "category_id", "author_id"]
        for field in required_fields:
            if not data.get(field):
                return JsonResponse(
                    {
                        "success": False,
                        "error": f'{field.replace("_", " ").title()} is required',
                    },
                    status=400,
                )

        # Clean and validate data
        article_data = {
            "title": data["title"].strip()[:300],
            "excerpt": data["excerpt"].strip()[:500],
            "category_id": data["category_id"],
            "author_id": data["author_id"],
            "featured_image_id": data.get("featured_image_id"),
            "status": data.get("status", "draft"),
            "meta_title": data.get("meta_title", "")[:60],
            "meta_description": data.get("meta_description", "")[:160],
            "tag_ids": data.get("tag_ids", []),
        }

        sections_data = data.get("content_sections", [])

        # Create or update article
        article_id = data.get("article_id")
        if article_id:
            article = get_object_or_404(Article, id=article_id)
            # Update existing article
            for key, value in article_data.items():
                if key != "tag_ids":
                    setattr(article, key, value)
            article.last_modified_by = request.user
            article.save()

            if article_data["tag_ids"]:
                article.tags.set(article_data["tag_ids"])
        else:
            # Create new article
            article = ArticleManager.create_article_with_sections(
                article_data, sections_data, request.user
            )

        logger.info(f"Article '{article.title}' saved by {request.user.username}")

        return JsonResponse(
            {
                "success": True,
                "article_id": str(article.id),
                "message": "Article saved successfully",
                "url": f"/dashboard/article/{article.id}/edit/",
            }
        )

    except Exception as e:
        logger.error(f"Error saving article by {request.user.username}: {str(e)}")
        return JsonResponse(
            {"success": False, "error": "An error occurred while saving the article"},
            status=500,
        )


@csrf_exempt
@ajax_admin_required
@require_http_methods(["POST"])
def upload_file_ajax(request):
    """Handle file upload and processing - Protected"""
    try:
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return JsonResponse(
                {"success": False, "error": "No file uploaded"}, status=400
            )

        # Process file based on type
        file_extension = uploaded_file.name.split(".")[-1].lower()

        if file_extension in ["pdf", "doc", "docx", "txt"]:
            # Process document and extract content
            processed_file = FileProcessor.process_file(uploaded_file)

            if processed_file["success"]:
                # Generate article structure
                article_data = ContentGenerator.generate_article_from_file(
                    processed_file
                )

                logger.info(
                    f"Document processed by {request.user.username}: {uploaded_file.name}"
                )

                return JsonResponse(
                    {
                        "success": True,
                        "file_type": "document",
                        "article_data": article_data,
                        "message": "File processed successfully",
                    }
                )
            else:
                return JsonResponse(
                    {"success": False, "error": processed_file["error"]}, status=400
                )

        else:
            # Handle media file upload
            media = MediaOptimizer.upload_and_optimize(uploaded_file, request.user)

            logger.info(f"Media uploaded by {request.user.username}: {media.title}")

            return JsonResponse(
                {
                    "success": True,
                    "file_type": "media",
                    "media": {
                        "id": str(media.id),
                        "title": media.title,
                        "url": media.cloudinary_url,
                        "file_type": media.file_type,
                        "file_size": media.file_size_formatted,
                    },
                    "message": "Media uploaded successfully",
                }
            )

    except Exception as e:
        logger.error(f"Error uploading file by {request.user.username}: {str(e)}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@csrf_exempt
@ajax_admin_required
@require_http_methods(["DELETE"])
def delete_media_ajax(request, media_id):
    """Delete media file - Protected"""
    try:
        media = get_object_or_404(CloudinaryMedia, id=media_id)

        # Delete from Cloudinary
        from core.utils.cloudinary_utils import CloudinaryManager

        delete_result = CloudinaryManager.delete_file(
            media.cloudinary_public_id,
            resource_type="image" if media.file_type == "image" else "raw",
        )

        if delete_result["success"]:
            media_title = media.title
            media.delete()

            logger.info(f"Media deleted by {request.user.username}: {media_title}")

            return JsonResponse(
                {"success": True, "message": "Media deleted successfully"}
            )
        else:
            return JsonResponse(
                {"success": False, "error": "Failed to delete from Cloudinary"},
                status=500,
            )

    except Exception as e:
        logger.error(f"Error deleting media by {request.user.username}: {str(e)}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@csrf_exempt
@ajax_admin_required
@require_http_methods(["GET"])
def get_dashboard_stats_ajax(request):
    """Get dashboard statistics via AJAX - Protected"""
    try:
        stats = DashboardStatsManager.get_overview_stats()
        return JsonResponse({"success": True, "stats": stats})
    except Exception as e:
        logger.error(
            f"Error getting dashboard stats for {request.user.username}: {str(e)}"
        )
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@csrf_exempt
@ajax_admin_required
@require_http_methods(["POST"])
def upload_file_view(request):
    """Enhanced file upload with proper response format"""
    try:
        # Validate file upload
        if "file" not in request.FILES:
            return JsonResponse(
                {"success": False, "error": "No file provided"}, status=400
            )

        file_obj = request.FILES["file"]

        # Validate file size (10MB limit)
        if file_obj.size > 10 * 1024 * 1024:
            return JsonResponse(
                {"success": False, "error": "File too large. Maximum size is 10MB."},
                status=400,
            )

        # Validate file type
        allowed_types = [
            "image/jpeg",
            "image/jpg",
            "image/png",
            "image/gif",
            "image/webp",
            "video/mp4",
            "application/pdf",
        ]
        if file_obj.content_type not in allowed_types:
            return JsonResponse(
                {"success": False, "error": "File type not allowed"}, status=400
            )

        # Extract title and metadata
        title = request.POST.get("title", file_obj.name.split(".")[0])

        # Determine file type based on content type
        if file_obj.content_type.startswith("image/"):
            file_type = "image"
        elif file_obj.content_type.startswith("video/"):
            file_type = "video"
        elif file_obj.content_type == "application/pdf":
            file_type = "document"
        else:
            file_type = "other"

        # Upload to Cloudinary
        try:
            # Use CloudinaryManager to upload
            upload_result = CloudinaryManager.upload_file(
                file_obj,
                folder="cisd/uploads",
            )

            if not upload_result["success"]:
                return JsonResponse(
                    {"success": False, "error": upload_result["error"]}, status=500
                )

            # Create CloudinaryMedia instance
            media = CloudinaryMedia.objects.create(
                title=title,
                cloudinary_url=upload_result["url"],
                cloudinary_public_id=upload_result["public_id"],
                file_type=file_type,
                file_format=upload_result.get("format", ""),
                file_size=file_obj.size,
                width=upload_result.get("width"),
                height=upload_result.get("height"),
                alt_text=request.POST.get("alt_text", ""),
                caption=request.POST.get("caption", ""),
                tags=request.POST.get("tags", ""),
                uploaded_by=request.user,
            )

            logger.info(f"File uploaded by {request.user.username}: {media.title}")

            return JsonResponse(
                {
                    "success": True,
                    "message": "File uploaded successfully",
                    "media": {
                        "id": str(media.id),
                        "title": media.title,
                        "cloudinary_url": media.cloudinary_url,
                        "file_type": media.file_type,
                        "file_size": media.file_size_formatted,
                    },
                }
            )

        except Exception as cloudinary_error:
            logger.error(f"Cloudinary upload failed: {str(cloudinary_error)}")
            return JsonResponse(
                {"success": False, "error": f"Upload failed: {str(cloudinary_error)}"},
                status=500,
            )

    except Exception as e:
        logger.error(f"Upload failed for {request.user.username}: {str(e)}")
        return JsonResponse(
            {"success": False, "error": f"Upload failed: {str(e)}"}, status=500
        )


@ajax_admin_required
@require_http_methods(["POST", "DELETE"])
def delete_media_view(request, media_id):
    """Enhanced media deletion with proper auth - Protected"""
    try:
        media = CloudinaryMedia.objects.get(id=media_id)

        # Check permissions (optional)
        if request.user != media.uploaded_by and not request.user.is_staff:
            return JsonResponse(
                {"success": False, "error": "Permission denied"}, status=403
            )

        # Delete from Cloudinary
        delete_result = CloudinaryManager.delete_file(
            media.cloudinary_public_id,
            "raw" if media.file_type == "document" else media.file_type,
        )

        # Delete from database
        media_title = media.title
        media.delete()

        logger.info(f"Media deleted by {request.user.username}: {media_title}")

        return JsonResponse(
            {"success": True, "message": "Media file deleted successfully"}
        )

    except CloudinaryMedia.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "Media file not found"}, status=404
        )
    except Exception as e:
        logger.error(f"Delete failed for {request.user.username}: {str(e)}")
        return JsonResponse(
            {"success": False, "error": f"Delete failed: {str(e)}"}, status=500
        )


# Additional Protected Views (continue with the same pattern...)


@ajax_admin_required
@require_http_methods(["POST"])
def bulk_articles_view(request):
    """Handle bulk operations on articles - Protected"""
    try:
        data = json.loads(request.body)
        article_ids = data.get("article_ids", [])
        action = data.get("action")

        if not article_ids or not action:
            return JsonResponse(
                {"success": False, "error": "Missing article IDs or action"}, status=400
            )

        articles = Article.objects.filter(id__in=article_ids)

        if action == "publish":
            articles.update(status="published", published_date=timezone.now())
        elif action == "draft":
            articles.update(status="draft")
        elif action == "archive":
            articles.update(status="archived")
        elif action == "delete":
            articles.delete()
        else:
            return JsonResponse(
                {"success": False, "error": "Invalid action"}, status=400
            )

        logger.info(
            f"Bulk action '{action}' on {len(article_ids)} articles by {request.user.username}"
        )

        return JsonResponse(
            {
                "success": True,
                "message": f"Successfully {action}ed {len(article_ids)} article(s)",
            }
        )

    except Exception as e:
        logger.error(f"Bulk operation failed for {request.user.username}: {str(e)}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@csrf_exempt
@ajax_admin_required
@require_http_methods(["POST"])
def save_article_view(request):
    """Enhanced save article view that handles both create and update - Protected"""
    try:
        data = json.loads(request.body)

        # Extract data with proper validation
        article_id = data.get("id") or data.get("article_id")
        title = data.get("title", "").strip()
        excerpt = data.get("excerpt", "").strip()
        category_id = data.get("category_id")
        author_id = data.get("author_id")
        featured_image_id = data.get("featured_image_id")
        status = data.get("status", "draft")
        content = data.get("content", "")
        meta_title = data.get("meta_title", "")
        meta_description = data.get("meta_description", "")
        meta_keywords = data.get("meta_keywords", "")
        tags = data.get("tags", [])
        publication_date = data.get("publication_date", "")

        # Basic validation
        if not title:
            return JsonResponse(
                {"success": False, "error": "Article title is required"}, status=400
            )

        # Validate required foreign keys
        if not author_id:
            # Default to current user if no author specified and user has an author profile
            try:
                default_author = Author.objects.filter(user=request.user).first()
                if default_author:
                    author_id = str(default_author.id)
                else:
                    return JsonResponse(
                        {"success": False, "error": "Author is required"}, status=400
                    )
            except:
                return JsonResponse(
                    {"success": False, "error": "Author is required"}, status=400
                )

        if not category_id:
            return JsonResponse(
                {"success": False, "error": "Category is required"}, status=400
            )

        # Get or create article
        with transaction.atomic():
            if article_id:
                try:
                    article = Article.objects.get(id=article_id)
                    message = "Article updated successfully"
                    is_update = True
                except Article.DoesNotExist:
                    return JsonResponse(
                        {"success": False, "error": "Article not found"}, status=404
                    )
            else:
                article = Article(created_by=request.user)
                message = "Article created successfully"
                is_update = False

            # Update article fields
            article.title = title
            article.excerpt = excerpt
            article.status = status
            article.meta_title = meta_title
            article.meta_description = meta_description
            article.meta_keywords = meta_keywords
            article.last_modified_by = request.user

            # Handle foreign key relationships with proper validation
            try:
                article.category = Category.objects.get(id=category_id)
            except (Category.DoesNotExist, ValueError):
                return JsonResponse(
                    {"success": False, "error": "Invalid category selected"}, status=400
                )

            try:
                article.author = Author.objects.get(id=author_id)
            except (Author.DoesNotExist, ValueError):
                return JsonResponse(
                    {"success": False, "error": "Invalid author selected"}, status=400
                )

            # Handle featured image
            if featured_image_id:
                if featured_image_id.startswith("http"):
                    # This is a URL, find the media by URL
                    try:
                        article.featured_image = CloudinaryMedia.objects.filter(
                            cloudinary_url=featured_image_id
                        ).first()
                    except:
                        article.featured_image = None
                else:
                    # This should be an ID
                    try:
                        article.featured_image = CloudinaryMedia.objects.get(
                            id=featured_image_id
                        )
                    except (CloudinaryMedia.DoesNotExist, ValueError):
                        article.featured_image = None
            else:
                article.featured_image = None

            # Handle publication date
            if publication_date:
                try:
                    from django.utils.dateparse import parse_datetime

                    parsed_date = parse_datetime(publication_date)
                    if parsed_date:
                        if status == "published":
                            article.published_date = parsed_date
                        elif status == "scheduled":
                            article.scheduled_publish_date = parsed_date
                except:
                    pass

            # Set published date if publishing for the first time
            if status == "published" and not article.published_date:
                article.published_date = timezone.now()

            # Save article
            article.save()

            # Handle content - store in a single ContentSection or update existing
            if content and content.strip():
                # Clear existing sections for updates, or create new one
                if is_update:
                    ContentSection.objects.filter(article=article).delete()

                # Create a single content section with the HTML content
                ContentSection.objects.create(
                    article=article,
                    section_type="paragraph",
                    order=0,
                    content=content,
                    title="Main Content",
                )

            # Handle tags
            if tags and isinstance(tags, list):
                article.tags.clear()

                for tag_name in tags:
                    if tag_name.strip():
                        tag, created = Tag.objects.get_or_create(
                            name=tag_name.strip(),
                            defaults={
                                "slug": tag_name.strip().lower().replace(" ", "-")
                            },
                        )
                        article.tags.add(tag)

        logger.info(f"Article '{title}' saved by {request.user.username}")

        return JsonResponse(
            {
                "success": True,
                "message": message,
                "article_id": str(article.id),
                "status": article.status,
                "is_update": is_update,
                "edit_url": f"/dashboard/article/{article.id}/edit/",
                "view_url": f"/article/{article.slug}/",
            }
        )

    except json.JSONDecodeError:
        return JsonResponse(
            {"success": False, "error": "Invalid JSON data"}, status=400
        )
    except Exception as e:
        logger.error(f"Failed to save article for {request.user.username}: {str(e)}")
        return JsonResponse(
            {"success": False, "error": f"Failed to save article: {str(e)}"}, status=500
        )


@ajax_admin_required
@require_http_methods(["POST", "DELETE"])
def delete_article_view(request, article_id):
    """Delete a single article - Protected"""
    try:
        article = get_object_or_404(Article, id=article_id)

        # Check permissions (optional - you might want only authors or admins to delete)
        if not request.user.is_staff and article.created_by != request.user:
            return JsonResponse(
                {"success": False, "error": "Permission denied"}, status=403
            )

        article_title = article.title
        article.delete()

        logger.info(f"Article '{article_title}' deleted by {request.user.username}")

        return JsonResponse(
            {
                "success": True,
                "message": f'Article "{article_title}" deleted successfully',
            }
        )

    except Article.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "Article not found"}, status=404
        )
    except Exception as e:
        logger.error(f"Failed to delete article for {request.user.username}: {str(e)}")
        return JsonResponse(
            {"success": False, "error": f"Failed to delete article: {str(e)}"},
            status=500,
        )


@ajax_admin_required
@require_http_methods(["POST"])
def toggle_featured_view(request, article_id):
    """Toggle the featured status of an article - Protected"""
    try:
        data = json.loads(request.body)
        is_featured = data.get("is_featured", False)

        article = get_object_or_404(Article, id=article_id)
        article.is_featured = is_featured
        article.last_modified_by = request.user
        article.save(update_fields=["is_featured", "updated_at", "last_modified_by"])

        status_text = "featured" if is_featured else "removed from featured"

        logger.info(
            f"Article '{article.title}' {status_text} by {request.user.username}"
        )

        return JsonResponse(
            {
                "success": True,
                "message": f'Article "{article.title}" {status_text}',
                "is_featured": article.is_featured,
            }
        )

    except Article.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "Article not found"}, status=404
        )
    except json.JSONDecodeError:
        return JsonResponse(
            {"success": False, "error": "Invalid JSON data"}, status=400
        )
    except Exception as e:
        logger.error(f"Failed to update article for {request.user.username}: {str(e)}")
        return JsonResponse(
            {"success": False, "error": f"Failed to update article: {str(e)}"},
            status=500,
        )


@ajax_admin_required
@require_http_methods(["POST"])
def duplicate_article_view(request, article_id):
    """Create a duplicate copy of an article - Protected"""
    try:
        original_article = get_object_or_404(Article, id=article_id)

        # Create new article with copied data
        new_article = Article(
            title=f"{original_article.title} (Copy)",
            excerpt=original_article.excerpt,
            category=original_article.category,
            author=original_article.author,
            featured_image=original_article.featured_image,
            status="draft",  # Always create as draft
            meta_title=original_article.meta_title,
            meta_description=original_article.meta_description,
            meta_keywords=original_article.meta_keywords,
            social_title=original_article.social_title,
            social_description=original_article.social_description,
            allow_comments=original_article.allow_comments,
            created_by=request.user,
            last_modified_by=request.user,
        )
        new_article.save()

        # Copy tags
        new_article.tags.set(original_article.tags.all())

        # Copy content sections
        original_sections = original_article.content_sections.all().order_by("order")
        for section in original_sections:
            ContentSection.objects.create(
                article=new_article,
                section_type=section.section_type,
                order=section.order,
                content=section.content,
                title=section.title,
                media_file=section.media_file,
                caption=section.caption,
                alt_text=section.alt_text,
                question=section.question,
                answer=section.answer,
                interviewer=section.interviewer,
                interviewee=section.interviewee,
                list_items=section.list_items,
                table_data=section.table_data,
                embed_code=section.embed_code,
                css_classes=section.css_classes,
                background_color=section.background_color,
                is_visible=section.is_visible,
                is_expandable=section.is_expandable,
            )

        logger.info(
            f"Article '{original_article.title}' duplicated by {request.user.username}"
        )

        return JsonResponse(
            {
                "success": True,
                "message": f"Article duplicated successfully",
                "new_article_id": str(new_article.id),
                "new_article_title": new_article.title,
            }
        )

    except Article.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "Original article not found"}, status=404
        )
    except Exception as e:
        logger.error(
            f"Failed to duplicate article for {request.user.username}: {str(e)}"
        )
        return JsonResponse(
            {"success": False, "error": f"Failed to duplicate article: {str(e)}"},
            status=500,
        )


@ajax_admin_required
@require_http_methods(["GET"])
def dashboard_stats_view(request):
    """Get dashboard statistics for the home page - Protected"""
    try:
        from datetime import datetime, timedelta

        from django.db.models import Count, Q

        # Article statistics
        total_articles = Article.objects.count()
        published_articles = Article.objects.filter(status="published").count()
        draft_articles = Article.objects.filter(status="draft").count()
        review_articles = Article.objects.filter(status="review").count()

        # This month's articles
        this_month = datetime.now().replace(day=1)
        articles_this_month = Article.objects.filter(created_at__gte=this_month).count()

        # Media statistics
        total_media = CloudinaryMedia.objects.count()

        # User/subscriber statistics (you might not have these models yet)
        total_subscribers = 0  # Update when you add newsletter functionality
        new_subscribers = 0

        # View statistics (you might want to implement view tracking)
        total_views = sum(article.view_count for article in Article.objects.all())

        stats = {
            "articles": {
                "total": total_articles,
                "published": published_articles,
                "draft": draft_articles,
                "review": review_articles,
                "this_month": articles_this_month,
            },
            "content": {"total_views": total_views},
            "users": {
                "total_subscribers": total_subscribers,
                "new_subscribers": new_subscribers,
            },
            "media": {"total_files": total_media},
            "events": {"upcoming": 0},  # Update when you add events functionality
        }

        return JsonResponse({"success": True, "stats": stats})

    except Exception as e:
        logger.error(f"Failed to get stats for {request.user.username}: {str(e)}")
        return JsonResponse(
            {"success": False, "error": f"Failed to get stats: {str(e)}"}, status=500
        )


@csrf_exempt
@ajax_admin_required
@require_http_methods(["POST"])
def create_category_view(request):
    """Create a new category via AJAX - Protected"""
    try:
        data = json.loads(request.body)

        # Extract and validate data
        name = data.get("name", "").strip().lower()
        display_name = data.get("display_name", "").strip()
        description = data.get("description", "").strip()
        color_code = data.get("color_code", "#dc2626").strip()

        # Validate required fields
        if not name or not display_name:
            return JsonResponse(
                {
                    "success": False,
                    "error": "Category name and display name are required",
                },
                status=400,
            )

        # Validate category name format (only lowercase letters, numbers, underscores)
        import re

        if not re.match(r"^[a-z0-9_]+$", name):
            return JsonResponse(
                {
                    "success": False,
                    "error": "Category name can only contain lowercase letters, numbers, and underscores",
                },
                status=400,
            )

        # Check if category already exists
        if Category.objects.filter(name=name).exists():
            return JsonResponse(
                {"success": False, "error": "Category with this name already exists"},
                status=400,
            )

        # Validate color code
        if not re.match(r"^#[0-9a-fA-F]{6}$", color_code):
            color_code = "#dc2626"  # Default color if invalid

        # Create category
        category = Category.objects.create(
            name=name,
            display_name=display_name,
            description=description,
            color_code=color_code,
            is_active=True,
            sort_order=Category.objects.count(),  # Add at end
        )

        logger.info(f"Category '{display_name}' created by {request.user.username}")

        return JsonResponse(
            {
                "success": True,
                "message": "Category created successfully",
                "category": {
                    "id": str(category.id),
                    "name": category.name,
                    "display_name": category.display_name,
                    "color_code": category.color_code,
                },
            }
        )

    except json.JSONDecodeError:
        return JsonResponse(
            {"success": False, "error": "Invalid JSON data"}, status=400
        )
    except Exception as e:
        logger.error(f"Error creating category by {request.user.username}: {str(e)}")
        return JsonResponse(
            {"success": False, "error": "An error occurred while creating category"},
            status=500,
        )


@csrf_exempt
@ajax_admin_required
@require_http_methods(["POST"])
def create_author_view(request):
    """Create a new author via AJAX - Protected"""
    try:
        data = json.loads(request.body)

        # Extract and validate data
        name = data.get("name", "").strip()
        title = data.get("title", "").strip()
        email = data.get("email", "").strip()
        bio = data.get("bio", "").strip()

        # Validate required fields
        if not name:
            return JsonResponse(
                {"success": False, "error": "Author name is required"}, status=400
            )

        # Check if author already exists
        if Author.objects.filter(name=name).exists():
            return JsonResponse(
                {"success": False, "error": "Author with this name already exists"},
                status=400,
            )

        # Validate email if provided
        if email:
            try:
                validate_email(email)
                # Check if email already exists
                if Author.objects.filter(email=email).exists():
                    return JsonResponse(
                        {
                            "success": False,
                            "error": "Author with this email already exists",
                        },
                        status=400,
                    )
            except ValidationError:
                return JsonResponse(
                    {"success": False, "error": "Invalid email address"}, status=400
                )

        # Create author
        author = Author.objects.create(
            name=name,
            title=title,
            email=email,
            bio=bio,
            is_active=True,
            sort_order=Author.objects.count(),  # Add at end
        )

        logger.info(f"Author '{name}' created by {request.user.username}")

        return JsonResponse(
            {
                "success": True,
                "message": "Author created successfully",
                "author": {
                    "id": str(author.id),
                    "name": author.name,
                    "title": author.title,
                    "email": author.email,
                },
            }
        )

    except json.JSONDecodeError:
        return JsonResponse(
            {"success": False, "error": "Invalid JSON data"}, status=400
        )
    except Exception as e:
        logger.error(f"Error creating author by {request.user.username}: {str(e)}")
        return JsonResponse(
            {"success": False, "error": "An error occurred while creating author"},
            status=500,
        )
